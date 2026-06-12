from sqlmodel import Session

from app.services.history_answer_question_service import (
    compare_strings,
    get_filtered_history,
)


def get_user_answer_history(
    session: Session,
    learner_id: int,
    *,
    lesson_id: int | None = None,
    topic_id: int | None = None,
    since_days: int | None = None,
    limit: int = 20,
):
    rows = get_filtered_history(
        session,
        learner_id,
        lesson_id=lesson_id,
        topic_id=topic_id,
        since_days=since_days,
        limit=limit,
    )

    history_items = [_row_to_dict(r) for r in rows]
    accuracy = _compute_accuracy(history_items)

    return {
        "ok": True,
        "tool": "get_user_answer_history",
        "summary": (
            f"User has {len(history_items)} answer history records "
            f"and an accuracy of {accuracy:.2%}"
        ),
        "data": {
            "total_records": len(history_items),
            "accuracy": accuracy,
            "filters": {
                "lesson_id": lesson_id,
                "topic_id": topic_id,
                "since_days": since_days,
                "limit": limit,
            },
            "history": history_items,
        },
    }


def _row_to_dict(row) -> dict:
    mapping = getattr(row, "_mapping", None)
    get = (
        (lambda k: mapping[k])
        if mapping is not None
        else (lambda k, r=row: getattr(r, k))
    )
    timesecond = get("timesecond")
    return {
        "id": get("history_id"),
        "timesecond": timesecond.isoformat() if timesecond else None,
        "question": get("question"),
        "user_answer": get("user_answer"),
        "correct_answer": get("correct_answer"),
        "type": get("q_type"),
        "difficulty": get("difficulty"),
        "lesson_id": get("lesson_id"),
        "lesson_name": get("lesson_name"),
        "topic_id": get("topic_id"),
        "topic_name": get("topic_name"),
    }


def _compute_accuracy(history: list[dict]) -> float:
    if not history:
        return 0.0
    correct = sum(
        1
        for h in history
        if compare_strings(h.get("correct_answer") or "", h.get("user_answer") or "")
    )
    return correct / len(history)
