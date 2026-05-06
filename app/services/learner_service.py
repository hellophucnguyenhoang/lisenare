from sqlmodel import Session, select

from app.database import Learner


def get_learner_by_id(session: Session, id: int) -> Learner:
    statement = select(Learner).where(Learner.id == id)
    return session.exec(statement).first()


def update_learner_full_name(
    session: Session, learner: Learner, full_name: str
):
    print(f"{full_name = }")
    if learner.full_name == full_name.strip():
        print("same full_name")
        return learner
    print("diff full_name")
    learner.full_name = full_name.strip()
    session.add(learner)
    session.commit()
    session.refresh(learner)
    return learner
