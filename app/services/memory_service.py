from sqlmodel import Session, desc, select

from app.database import MistakeMemory


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


def has_mistake_for_question(
    session: Session, learner_id: int, question_id: int
) -> bool:
    """Check learner đã có MistakeMemory cho question_id này chưa.
    Dựa vào prefix [qid:X] trong content do batch_analyze ghi vào."""
    pattern = f"[qid:{int(question_id)}]%"
    statement = (
        select(MistakeMemory.id)
        .where(MistakeMemory.learner_id == learner_id)
        .where(MistakeMemory.content.like(pattern))
        .limit(1)
    )
    return session.exec(statement).first() is not None


def mistake_to_dict(m: MistakeMemory) -> dict:
    return {
        "id": m.id,
        "mistake_type": m.mistake_type,
        "content": m.content,
        "grammar_point": m.grammar_point,
        "suggested_fix": m.suggested_fix,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
