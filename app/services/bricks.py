from sqlmodel import Session, select
from sqlalchemy.sql import func
from app.database import Brick, CollectionBrick, Collection
from app.config import settings
from app.schemas import BrickUpdate
from pathlib import Path
from datetime import datetime, timezone
from fastapi import HTTPException

def get_brick(session: Session, id: int):
    """
    Return a Brick or None.
    """
    return session.exec(select(Brick).where(Brick.id == id)).first()

def iter_audio_file(filename: str):
    base_dir = Path(settings.brick_folder)
    file_path = (base_dir / filename).resolve()
    with open(file_path, "rb") as audio_file:
        yield from audio_file

def get_random_brick(session: Session, collection_id: int):
    statement = (
        select(Brick)
        .join(CollectionBrick)
        .where(CollectionBrick.collection_id == collection_id)
        .order_by(func.random())
        .limit(1)
    )
    return session.exec(statement).first()

def get_user_collections(session: Session, user_id: int):
    statement = (
        select(Collection)
        .where(Collection.creator_id == user_id)
    )
    return session.exec(statement).all()

def update_brick(
    session: Session,
    brick_id: int,
    brick_update: BrickUpdate,
    user_id: int,
) -> Brick:
    brick = session.get(Brick, brick_id)

    if not brick:
        raise HTTPException(status_code=404, detail="Brick not found")

    if brick.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed to edit this brick")

    data = brick_update.model_dump(exclude_unset=True)

    for key, value in data.items():
        setattr(brick, key, value)
    brick.last_edit_at = datetime.now(timezone.utc)

    session.add(brick)
    session.commit()
    session.refresh(brick)

    return brick