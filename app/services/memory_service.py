from datetime import datetime, timezone

from sqlmodel import Session, desc, select

from app.database import LearnerPreference, MistakeMemory


def add_mistake(
    session: Session,
    learner_id: int,
    mistake_type: str,
    content: str,
    grammar_point: str | None = None,
    suggested_fix: str | None = None,
) -> MistakeMemory:
    record = MistakeMemory(
        learner_id=learner_id,
        mistake_type=mistake_type,
        content=content,
        grammar_point=grammar_point,
        suggested_fix=suggested_fix,
    )
    session.add(record)
    try:
        session.commit()
        session.refresh(record)
    except Exception as exc:
        session.rollback()
        print(f"add_mistake failed: {exc}")
        raise
    return record


def get_recent_mistakes(
    session: Session, learner_id: int, limit: int = 5
) -> list[MistakeMemory]:
    statement = (
        select(MistakeMemory)
        .where(MistakeMemory.learner_id == learner_id)
        .order_by(desc(MistakeMemory.created_at))
        .limit(limit)
    )
    return list(session.exec(statement).all())


def mistake_to_dict(m: MistakeMemory) -> dict:
    return {
        "id": m.id,
        "mistake_type": m.mistake_type,
        "content": m.content,
        "grammar_point": m.grammar_point,
        "suggested_fix": m.suggested_fix,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def get_preferences(
    session: Session, learner_id: int
) -> LearnerPreference | None:
    statement = select(LearnerPreference).where(
        LearnerPreference.learner_id == learner_id
    )
    return session.exec(statement).first()


def preferences_to_dict(p: LearnerPreference | None) -> dict:
    if p is None:
        return {
            "preferred_exercise_type": None,
            "learning_style": None,
            "goal": None,
            "notes": None,
            "updated_at": None,
        }
    return {
        "preferred_exercise_type": p.preferred_exercise_type,
        "learning_style": p.learning_style,
        "goal": p.goal,
        "notes": p.notes,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def set_preferences(
    session: Session,
    learner_id: int,
    *,
    preferred_exercise_type: str | None = None,
    learning_style: str | None = None,
    goal: str | None = None,
    notes: str | None = None,
) -> LearnerPreference:
    record = get_preferences(session, learner_id)
    now = datetime.now(timezone.utc)
    if record is None:
        record = LearnerPreference(
            learner_id=learner_id,
            preferred_exercise_type=preferred_exercise_type,
            learning_style=learning_style,
            goal=goal,
            notes=notes,
            updated_at=now,
        )
        session.add(record)
    else:
        if preferred_exercise_type is not None:
            record.preferred_exercise_type = preferred_exercise_type
        if learning_style is not None:
            record.learning_style = learning_style
        if goal is not None:
            record.goal = goal
        if notes is not None:
            record.notes = notes
        record.updated_at = now

    try:
        session.commit()
        session.refresh(record)
    except Exception as exc:
        session.rollback()
        print(f"set_preferences failed: {exc}")
        raise
    return record
