from sqlmodel import Session, select

from app.database import Learner


def get_learner_by_id(session: Session, id: int) -> Learner:
    statement = select(Learner).where(Learner.id == id)
    return session.exec(statement).first()


def update_learner_full_name(session: Session, learner: Learner, name: str):
    print(f"{name = }")
    if learner.name == name.strip():
        print("same name")
        return learner
    print("diff name")
    learner.name = name.strip()
    session.add(learner)
    session.commit()
    session.refresh(learner)
    return learner
