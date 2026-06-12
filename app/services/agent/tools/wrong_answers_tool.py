import json
import re

from sqlmodel import Session

from app.services import memory_service, mistake_cache_service
from app.services.history_answer_question_service import (
    compare_strings,
    get_filtered_history,
)
from app.services.llm_service import call_llm
from app.services.mistake_cache_service import normalize_answer


# ============================================================
# Helpers
# ============================================================

def _row_get(row, key: str):
    mapping = getattr(row, "_mapping", None)
    if mapping is not None and key in mapping:
        return mapping[key]
    return getattr(row, key, None)


def _difficulty_bucket(diff: float | None) -> str:
    if diff is None:
        return "medium"
    try:
        d = float(diff)
    except (TypeError, ValueError):
        return "medium"
    if d < 0:
        return "easy"
    if d <= 1:
        return "medium"
    return "hard"


def _collect_wrong_records(rows: list) -> tuple[list, dict[int, dict]]:
    """Đi qua các history row, đánh dấu sai bằng compare_strings.
    Trả về (raw_history, wrong_by_qid) — raw_history dùng để tính accuracy,
    wrong_by_qid là map question_id → record sai mới nhất."""
    wrong_by_qid: dict[int, dict] = {}

    for row in rows:
        correct_answer = _row_get(row, "correct_answer") or ""
        user_answer = _row_get(row, "user_answer") or ""
        is_wrong = not compare_strings(correct_answer, user_answer)
        if not is_wrong:
            continue
        qid = int(_row_get(row, "question_id"))
        # rows đã được order DESC theo timesecond → row đầu tiên là mới nhất
        if qid in wrong_by_qid:
            wrong_by_qid[qid]["wrong_count"] += 1
            continue
        wrong_by_qid[qid] = {
            "question_id": qid,
            "question": _row_get(row, "question"),
            "correct_answer": correct_answer,
            "last_user_answer": user_answer,
            "difficulty": _row_get(row, "difficulty"),
            "lesson_id": _row_get(row, "lesson_id"),
            "lesson_name": _row_get(row, "lesson_name"),
            "topic_id": _row_get(row, "topic_id"),
            "topic_name": _row_get(row, "topic_name"),
            "wrong_count": 1,
        }

    return rows, wrong_by_qid


# ============================================================
# Tool 1: aggregate_wrong_answers — không LLM
# ============================================================

def aggregate_wrong_answers(
    session: Session,
    learner_id: int,
    *,
    lesson_id: int | None = None,
    topic_id: int | None = None,
    since_days: int | None = None,
    limit: int = 50,
) -> dict:
    rows = get_filtered_history(
        session,
        learner_id,
        lesson_id=lesson_id,
        topic_id=topic_id,
        since_days=since_days,
        limit=max(1, min(int(limit or 50), 200)),
    )

    total = len(rows)
    correct = sum(
        1
        for row in rows
        if compare_strings(
            _row_get(row, "correct_answer") or "",
            _row_get(row, "user_answer") or "",
        )
    )
    wrong = total - correct
    accuracy = (correct / total) if total > 0 else 0.0

    _, wrong_by_qid = _collect_wrong_records(rows)
    wrong_questions = sorted(
        wrong_by_qid.values(),
        key=lambda x: x["wrong_count"],
        reverse=True,
    )

    by_difficulty = {"easy": 0, "medium": 0, "hard": 0}
    for w in wrong_questions:
        bucket = _difficulty_bucket(w.get("difficulty"))
        by_difficulty[bucket] = by_difficulty.get(bucket, 0) + 1

    return {
        "ok": True,
        "tool": "aggregate_wrong_answers",
        "summary": (
            f"{wrong}/{total} câu sai (accuracy {accuracy:.0%}), "
            f"{len(wrong_questions)} câu khác nhau"
        ),
        "data": {
            "total": total,
            "wrong": wrong,
            "correct": correct,
            "accuracy": accuracy,
            "filters": {
                "lesson_id": lesson_id,
                "topic_id": topic_id,
                "since_days": since_days,
                "limit": limit,
            },
            "wrong_questions": wrong_questions,
            "by_difficulty": by_difficulty,
        },
    }


# ============================================================
# Tool 2: batch_analyze_wrong_answers — LLM theo chunk + cache
# ============================================================

_BATCH_PROMPT = """Bạn là gia sư tiếng Anh. Phân tích các câu sai sau đây.

Trả về JSON array có ĐÚNG {n} phần tử, theo đúng thứ tự đầu vào, không thêm
chữ nào ngoài JSON, không markdown. Mỗi phần tử:
{{
  "question_id": <int>,
  "mistake_type": "grammar | vocabulary | spelling | logic | other",
  "grammar_point": "tên điểm ngữ pháp hoặc null",
  "explanation": "1-2 câu tiếng Việt giải thích vì sao sai",
  "suggested_fix": "đáp án/cách sửa đúng (tiếng Anh)"
}}

Đầu vào:
{items_json}
"""


def _extract_json_array(text: str) -> list | None:
    if not text:
        return None
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def _llm_analyze_chunk(chunk: list[dict]) -> list[dict]:
    """Gọi LLM 1 lần cho cả chunk, trả về list dict đã parse khớp thứ tự
    đầu vào (best-effort: nếu thiếu, retry 1 lần; nếu vẫn thiếu thì trả
    items có 'failed': True)."""
    items_json = json.dumps(
        [
            {
                "question_id": c["question_id"],
                "question": c["question"],
                "correct_answer": c["correct_answer"],
                "learner_answer": c["last_user_answer"],
            }
            for c in chunk
        ],
        ensure_ascii=False,
    )
    prompt = _BATCH_PROMPT.format(n=len(chunk), items_json=items_json)

    raw = call_llm(prompt)
    parsed = _extract_json_array(raw)
    if parsed is None or len(parsed) != len(chunk):
        # Retry 1 lần
        raw = call_llm(prompt)
        parsed = _extract_json_array(raw)

    out: list[dict] = []
    parsed_by_qid: dict[int, dict] = {}
    if parsed:
        for item in parsed:
            if isinstance(item, dict) and "question_id" in item:
                try:
                    parsed_by_qid[int(item["question_id"])] = item
                except (TypeError, ValueError):
                    continue

    for c in chunk:
        item = parsed_by_qid.get(c["question_id"])
        if item is None:
            out.append({"question_id": c["question_id"], "failed": True})
            continue

        gp = item.get("grammar_point")
        if isinstance(gp, str) and gp.lower() == "null":
            gp = None

        out.append(
            {
                "question_id": c["question_id"],
                "mistake_type": str(item.get("mistake_type") or "other"),
                "grammar_point": gp,
                "explanation": item.get("explanation") or "",
                "suggested_fix": item.get("suggested_fix"),
                "failed": False,
            }
        )
    return out


def batch_analyze_wrong_answers(
    session: Session,
    learner_id: int,
    *,
    lesson_id: int | None = None,
    topic_id: int | None = None,
    since_days: int | None = None,
    limit: int = 10,
    chunk_size: int = 8,
) -> dict:
    limit = max(1, min(int(limit or 10), 15))
    chunk_size = max(1, min(int(chunk_size or 8), 10))

    # Bước 1: lấy lịch sử để xác định câu sai
    rows = get_filtered_history(
        session,
        learner_id,
        lesson_id=lesson_id,
        topic_id=topic_id,
        since_days=since_days,
        limit=200,  # quét rộng hơn để có đủ câu sai
    )
    _, wrong_by_qid = _collect_wrong_records(rows)
    if not wrong_by_qid:
        return {
            "ok": True,
            "tool": "batch_analyze_wrong_answers",
            "summary": "Không có câu sai nào trong phạm vi filter",
            "data": {
                "total_wrong": 0,
                "from_cache": 0,
                "from_llm": 0,
                "skipped_already_in_memory": 0,
                "failed": 0,
                "llm_calls": 0,
                "results": [],
            },
        }

    candidates = list(wrong_by_qid.values())[:limit]

    # Bước 2: bỏ câu đã có trong MistakeMemory của learner
    pending: list[dict] = []
    skipped_results: list[dict] = []
    for c in candidates:
        if memory_service.has_mistake_for_question(
            session, learner_id, c["question_id"]
        ):
            skipped_results.append(
                {
                    "question_id": c["question_id"],
                    "skipped": True,
                    "source": "already_in_memory",
                    "memory_id": None,
                }
            )
            continue
        c["normalized_answer"] = normalize_answer(c.get("last_user_answer"))
        pending.append(c)

    # Bước 3: bulk lookup cache
    cache_map = mistake_cache_service.bulk_lookup_cache(
        session,
        keys=[(c["question_id"], c["normalized_answer"]) for c in pending],
    )

    cache_hit_items: list[dict] = []
    miss_items: list[dict] = []
    for c in pending:
        key = (c["question_id"], c["normalized_answer"])
        if key in cache_map:
            cache_hit_items.append(c)
        else:
            miss_items.append(c)

    results: list[dict] = list(skipped_results)
    from_cache = 0
    from_llm = 0
    failed = 0
    llm_calls = 0

    # Bước 4: xử lý cache HIT
    for c in cache_hit_items:
        cache_row = cache_map[(c["question_id"], c["normalized_answer"])]
        # ++hit_count
        try:
            mistake_cache_service.upsert_cache(
                session,
                question_id=c["question_id"],
                normalized_answer=c["normalized_answer"],
                mistake_type=cache_row.mistake_type,
                grammar_point=cache_row.grammar_point,
                explanation=cache_row.explanation,
                suggested_fix=cache_row.suggested_fix,
                increment_hit=True,
            )
        except Exception as exc:
            print(f"[batch_analyze] cache ++hit failed qid={c['question_id']}: {exc}")

        content = mistake_cache_service.cache_to_memory_content(
            cache_row,
            question_text=c["question"] or "",
            learner_answer=c["last_user_answer"] or "",
        )
        memory_id = None
        try:
            record = memory_service.add_mistake(
                session,
                learner_id=learner_id,
                mistake_type=cache_row.mistake_type,
                content=content,
                grammar_point=cache_row.grammar_point,
                suggested_fix=cache_row.suggested_fix,
            )
            memory_id = record.id
        except Exception as exc:
            print(f"[batch_analyze] save memory (cache) failed: {exc}")

        from_cache += 1
        results.append(
            {
                "question_id": c["question_id"],
                "mistake_type": cache_row.mistake_type,
                "grammar_point": cache_row.grammar_point,
                "source": "cache",
                "skipped": False,
                "memory_id": memory_id,
            }
        )

    # Bước 5: chunk LLM cho miss
    for i in range(0, len(miss_items), chunk_size):
        chunk = miss_items[i : i + chunk_size]
        llm_calls += 1
        chunk_results = _llm_analyze_chunk(chunk)

        for c, r in zip(chunk, chunk_results):
            if r.get("failed"):
                failed += 1
                results.append(
                    {
                        "question_id": c["question_id"],
                        "skipped": False,
                        "source": "llm",
                        "memory_id": None,
                        "failed": True,
                    }
                )
                continue

            try:
                mistake_cache_service.upsert_cache(
                    session,
                    question_id=c["question_id"],
                    normalized_answer=c["normalized_answer"],
                    mistake_type=r["mistake_type"],
                    grammar_point=r.get("grammar_point"),
                    explanation=r.get("explanation"),
                    suggested_fix=r.get("suggested_fix"),
                    increment_hit=False,
                )
            except Exception as exc:
                print(
                    f"[batch_analyze] cache insert failed qid={c['question_id']}: {exc}"
                )

            content = (
                f"[qid:{c['question_id']}] "
                f"Q: {c['question']}\n"
                f"Learner: {c['last_user_answer']}\n"
                f"Explain: {r.get('explanation') or ''}"
            )
            memory_id = None
            try:
                record = memory_service.add_mistake(
                    session,
                    learner_id=learner_id,
                    mistake_type=r["mistake_type"],
                    content=content,
                    grammar_point=r.get("grammar_point"),
                    suggested_fix=r.get("suggested_fix"),
                )
                memory_id = record.id
            except Exception as exc:
                print(f"[batch_analyze] save memory (llm) failed: {exc}")

            from_llm += 1
            results.append(
                {
                    "question_id": c["question_id"],
                    "mistake_type": r["mistake_type"],
                    "grammar_point": r.get("grammar_point"),
                    "source": "llm",
                    "skipped": False,
                    "memory_id": memory_id,
                }
            )

    return {
        "ok": True,
        "tool": "batch_analyze_wrong_answers",
        "summary": (
            f"Phân tích {from_cache + from_llm} câu "
            f"(cache_hit={from_cache}, llm_call={llm_calls} chunk), "
            f"bỏ qua {len(skipped_results)}, lỗi {failed}"
        ),
        "data": {
            "total_wrong": len(candidates),
            "from_cache": from_cache,
            "from_llm": from_llm,
            "skipped_already_in_memory": len(skipped_results),
            "failed": failed,
            "llm_calls": llm_calls,
            "results": results,
        },
    }
