from sqlmodel import Session, select, delete
from sqlalchemy.sql import func
from app.database import Brick, CollectionBrick
from app.config import settings
from app.schemas import BrickUpdate, BrickCreate
from pathlib import Path
from datetime import datetime, timezone
from fastapi import HTTPException, status, UploadFile

def get_brick(session: Session, id: int) -> Brick:
    brick = session.exec(select(Brick).where(Brick.id == id)).first()
    if not brick:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brick not found")
    return brick

def iter_audio_file(filename: str):
    base_dir = Path(settings.brick_folder)
    file_path = (base_dir / filename).resolve()
    with open(file_path, "rb") as audio_file:
        yield from audio_file

def get_random_brick(session: Session, learner_id: int, collection_id: int) -> Brick:
    statement = (
        select(Brick)
        .join(CollectionBrick)
        .where(CollectionBrick.collection_id == collection_id and Brick.creator_id == learner_id)
        .order_by(func.random())
        .limit(1)
    )
    return session.exec(statement).first()

def update_brick(
    session: Session,
    brick_id: int,
    brick_update: BrickUpdate,
    user_id: int,
) -> Brick:
    brick = session.get(Brick, brick_id)
    if not brick:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brick not found")
    if brick.creator_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User are not allowed to edit this brick")
    
    data = brick_update.model_dump(exclude_unset=True, exclude={"collection_ids"})
    for key, value in data.items():
        setattr(brick, key, value)

    if brick_update.collection_ids:
        session.exec(
            delete(CollectionBrick)
            .where(CollectionBrick.brick_id == brick_id)
        )
        for collection_id in brick_update.collection_ids:
            link = CollectionBrick(collection_id=collection_id, brick_id=brick_id)
            session.add(link)

    brick.last_edit_at = datetime.now(timezone.utc)
    session.add(brick)
    session.commit()
    session.refresh(brick)
    return brick

def create_brick(session: Session, brick_create: BrickCreate) -> Brick:
    db_brick = Brick.model_validate(brick_create)
    session.add(db_brick)
    session.commit()
    session.refresh(db_brick)
    return db_brick
