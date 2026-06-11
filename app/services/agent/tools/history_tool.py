from app.services.history_answer_question_service import get_history_by_learner
from sqlmodel import Session


def get_user_answer_history(session: Session, learner_id: int):
    history_list = get_history_by_learner(session, learner_id)
    accuracy = get_accuracy(history_list)
    return {
        "ok": True,
        "tool": "get_user_answer_history",
        "summary": (
            f"User has {len(history_list)} answer history records "
            f"and an accuracy of {accuracy:.2%}"
        ),
        "data": {
            "total_records": len(history_list),
            "accuracy": accuracy,
            "history": [convert_history(history) for history in history_list],
        },
    }


def convert_history(history):
    if history is None:
        return None
    return {
        "id": history.id,
        "timesecond": (
            history.timesecond.isoformat() if history.timesecond else None
        ),
        "question": history.question,
        "answer": history.answer,
        "user_answer": history.user_answer,
        "difficulty": history.difficulty,
        "correct_answer": history.correct_answer,
    }


def get_accuracy(history):
    if not history:
        return 0.0
    correct_answers = sum(
        1
        for h in history
        if normalize_answer(h.correct_answer) == normalize_answer(h.user_answer)
    )
    return correct_answers / len(history)


def normalize_answer(answer: str | None) -> str:
    return (answer or "").strip().lower()
