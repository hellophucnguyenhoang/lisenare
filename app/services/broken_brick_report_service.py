from sqlmodel import Session, select

from app.database import BrokenBrickReport


def save_report(
    session: Session,
    reporter_id: int,
    brick_id: int,
    description: str | None = None,
) -> BrokenBrickReport:
    statement = select(BrokenBrickReport).where(
        BrokenBrickReport.learner_id == reporter_id,
        BrokenBrickReport.brick_id == brick_id,
    )
    existing = session.exec(statement).first()
    if existing:
        if description:
            existing.description = description
            session.commit()
            session.refresh(existing)
        return existing

    new_report = BrokenBrickReport(
        learner_id=reporter_id,
        brick_id=brick_id,
        description=description,
    )
    session.add(new_report)
    session.commit()
    session.refresh(new_report)
    return new_report


def get_reported_brick_ids(session: Session, learner_id: int) -> set[int]:
    statement = select(BrokenBrickReport.brick_id).where(
        BrokenBrickReport.learner_id == learner_id
    )
    broken_brick_ids = session.exec(statement)
    return set(broken_brick_ids)
