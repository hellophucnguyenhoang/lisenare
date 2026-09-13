from sqlmodel import Session, select

from app.database import Learner, LearnerSetting
from app.schemas import LearnerUpdate


def get_learner_by_id(session: Session, id: int) -> Learner:
    statement = select(Learner).where(Learner.id == id)
    return session.exec(statement).first()


def update_learner(
    session: Session,
    learner: Learner,
    data: LearnerUpdate,
) -> Learner:
    db_learner = session.get(Learner, learner.id) or learner
    if data.name is not None and data.name.strip():
        db_learner.name = data.name.strip()
        session.add(db_learner)

    if data.practice_lang is not None:
        setting = db_learner.setting
        if not setting and db_learner.id:
            setting = session.get(LearnerSetting, db_learner.id)
        if not setting:
            setting = LearnerSetting(learner_id=db_learner.id)
        setting.practice_lang = data.practice_lang.strip().lower()
        session.add(setting)
        db_learner.setting = setting

    session.commit()
    session.refresh(db_learner)
    if db_learner.setting:
        session.refresh(db_learner.setting)
    return db_learner
