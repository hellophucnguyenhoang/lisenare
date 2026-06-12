from datetime import datetime, timezone

from sqlalchemy import tuple_
from sqlmodel import Session, select

from app.database import MistakeCache


def normalize_answer(s: str | None) -> str:
    """Đồng thuận với compare_strings: split theo ',', strip + lower, sort
    để 'B, A' và 'a,b' cho cùng 1 key. Câu single-answer cũng đi qua đường
    này (split 1 phần tử)."""
    if s is None:
        return ""
    parts = [p.strip().lower() for p in str(s).split(",") if p.strip()]
    parts.sort()
    return ",".join(parts)


def lookup_cache(
    session: Session, question_id: int, normalized_answer: str
) -> MistakeCache | None:
    statement = (
        select(MistakeCache)
        .where(MistakeCache.question_id == question_id)
        .where(MistakeCache.normalized_answer == normalized_answer)
        .limit(1)
    )
    return session.exec(statement).first()


def bulk_lookup_cache(
    session: Session, keys: list[tuple[int, str]]
) -> dict[tuple[int, str], MistakeCache]:
    if not keys:
        return {}
    deduped = list({(int(qid), na) for qid, na in keys})
    statement = select(MistakeCache).where(
        tuple_(MistakeCache.question_id, MistakeCache.normalized_answer).in_(
            deduped
        )
    )
    rows = session.exec(statement).all()
    return {(row.question_id, row.normalized_answer): row for row in rows}


def upsert_cache(
    session: Session,
    *,
    question_id: int,
    normalized_answer: str,
    mistake_type: str,
    grammar_point: str | None = None,
    explanation: str | None = None,
    suggested_fix: str | None = None,
    increment_hit: bool = False,
) -> MistakeCache:
    """Insert mới nếu chưa có, hoặc tăng hit_count nếu đã có (khi
    increment_hit=True). Khi `increment_hit=True` các trường analysis
    không bị ghi đè để giữ phân tích đầu tiên."""
    existing = lookup_cache(session, question_id, normalized_answer)
    now = datetime.now(timezone.utc)

    if existing is not None:
        if increment_hit:
            existing.hit_count = (existing.hit_count or 0) + 1
            existing.updated_at = now
            try:
                session.commit()
                session.refresh(existing)
            except Exception as exc:
                session.rollback()
                print(f"upsert_cache (hit++) failed: {exc}")
                raise
        return existing

    record = MistakeCache(
        question_id=question_id,
        normalized_answer=normalized_answer,
        mistake_type=mistake_type,
        grammar_point=grammar_point,
        explanation=explanation,
        suggested_fix=suggested_fix,
        hit_count=1,
        created_at=now,
        updated_at=now,
    )
    session.add(record)
    try:
        session.commit()
        session.refresh(record)
    except Exception as exc:
        session.rollback()
        print(f"upsert_cache (insert) failed: {exc}")
        raise
    return record


def cache_to_memory_content(
    cache_row: MistakeCache,
    *,
    question_text: str,
    learner_answer: str,
    qid_prefix: bool = True,
) -> str:
    """Build chuỗi content cho MistakeMemory từ 1 cache row."""
    prefix = f"[qid:{cache_row.question_id}] " if qid_prefix else ""
    explanation = cache_row.explanation or "(no explanation)"
    return (
        f"{prefix}Q: {question_text}\n"
        f"Learner: {learner_answer}\n"
        f"Explain: {explanation}"
    )
