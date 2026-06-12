from sqlmodel import Session

from app.services import memory_service


def get_learner_preferences(session: Session, learner_id: int) -> dict:
    record = memory_service.get_preferences(session, learner_id)
    data = memory_service.preferences_to_dict(record)
    has_any = any(
        data.get(k)
        for k in (
            "preferred_exercise_type",
            "learning_style",
            "goal",
            "notes",
        )
    )
    return {
        "ok": True,
        "tool": "get_learner_preferences",
        "summary": (
            "Đã có preferences được lưu"
            if has_any
            else "Học viên chưa khai báo preferences"
        ),
        "data": data,
    }


def set_learner_preferences(
    session: Session,
    learner_id: int,
    preferred_exercise_type: str | None = None,
    learning_style: str | None = None,
    goal: str | None = None,
    notes: str | None = None,
) -> dict:
    if not any(
        v is not None
        for v in (preferred_exercise_type, learning_style, goal, notes)
    ):
        return {
            "ok": False,
            "tool": "set_learner_preferences",
            "summary": "Không có field nào được cập nhật",
            "error": "no fields provided",
        }

    record = memory_service.set_preferences(
        session,
        learner_id=learner_id,
        preferred_exercise_type=preferred_exercise_type,
        learning_style=learning_style,
        goal=goal,
        notes=notes,
    )
    return {
        "ok": True,
        "tool": "set_learner_preferences",
        "summary": "Đã cập nhật preferences",
        "data": memory_service.preferences_to_dict(record),
    }
