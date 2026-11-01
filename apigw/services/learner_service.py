from fastapi import status
from sqlmodel import Session, select

from cloud_storage_client import download_file
from config import logger, settings
from constants import ASSETS_DIR
from database import Learner, LearnerSetting
from exceptions import RequestException
from schemas import LearnerUpdate


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

    if data.avatar_path is not None:
        db_learner.avatar_path = data.avatar_path
        session.add(db_learner)

    if data.retrieval_lang is not None:
        setting = db_learner.setting
        if not setting and db_learner.id:
            setting = session.get(LearnerSetting, db_learner.id)
        if not setting:
            setting = LearnerSetting(learner_id=db_learner.id)
        setting.retrieval_lang = data.retrieval_lang.strip().lower()
        session.add(setting)
        db_learner.setting = setting

    session.commit()
    session.refresh(db_learner)
    if db_learner.setting:
        session.refresh(db_learner.setting)
    logger.info(f"Updated settings for learner ID: {db_learner.id}")
    return db_learner


def update_learner_avatar(
    session: Session,
    learner: Learner,
    avatar_path: str | None,
) -> Learner:
    db_learner = session.get(Learner, learner.id) or learner
    db_learner.avatar_path = avatar_path
    session.add(db_learner)
    session.commit()
    session.refresh(db_learner)
    logger.info(f"Updated avatar for learner ID: {db_learner.id}")
    return db_learner


def get_learner_avatar_url(
    session: Session,
    learner_id: int,
) -> str:
    """
    Ensure the learner's avatar file exists locally at lisenare-assets/<avatar_path>,
    downloading from cloud storage if needed, and return the full public URL.
    """
    learner = session.get(Learner, learner_id)
    if not learner:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Learner {learner_id} not found",
        )

    avatar_path = learner.avatar_path or "default-images/meo.webp"
    local_file = ASSETS_DIR / avatar_path
    if not local_file.is_file():
        download_file(avatar_path, local_file)

    base_url = settings.asset_base_url.rstrip("/")
    return f"{base_url}/{avatar_path.lstrip('/')}"
