import json
import re

from sqlmodel import Session

from app.services import memory_service
from app.services.history_answer_question_service import (
    compare_strings,
    get_filtered_history,
)
from app.services.llm_service import call_llm


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
    prompt = (
        "Bạn là gia sư tiếng Anh. Phân tích các câu sai sau đây.\n\n"
        f"Trả về JSON array có ĐÚNG {len(chunk)} phần tử, theo đúng thứ tự đầu vào, không thêm\n"
        "chữ nào ngoài JSON, không markdown. Mỗi phần tử:\n"
        "{\n"
        '  "question_id": <int>,\n'
        '  "mistake_type": "grammar | vocabulary | spelling | logic | other",\n'
        '  "grammar_point": "tên điểm ngữ pháp hoặc null",\n'
        '  "explanation": "1-2 câu tiếng Việt giải thích vì sao sai",\n'
        '  "suggested_fix": "đáp án/cách sửa đúng (tiếng Anh)"\n'
        "}\n\n"
        f"Đầu vào:\n{items_json}"
    )

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
