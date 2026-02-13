from sqlmodel import Session, select, delete
from sqlalchemy import func
from app.database import Brick, CollectionBrick, BrickMetadata
from app.config import settings
from app.schemas import BrickUpdate, BrickCreate, UnitType
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

def get_random_brick(
    session: Session,
    learner_id: int,
    collection_ids: list[int] | None = None,
) -> Brick | None:

    statement = (
        select(Brick)
        .join(CollectionBrick)
        .join(BrickMetadata)
        .where(
            Brick.creator_id == learner_id, 
            BrickMetadata.unit_type == UnitType.sentence
        )
    )

    if collection_ids:
        statement = statement.where(
            CollectionBrick.collection_id.in_(collection_ids)
        )

    statement = (
        statement
        .order_by(func.random())
        .limit(1)
    )

    return session.exec(statement).first()

def get_brick_learn(
    session: Session,
    learner_id: int,
    collection_id: int,
    brick_order: int = 1,  # Assuming 1-based index (1st, 2nd...)
) -> Brick | None:
    brick_statement = (
        select(Brick)
        .join(CollectionBrick)
        .where(
            Brick.creator_id == learner_id, 
            CollectionBrick.collection_id == collection_id
        )
        .order_by(func.length(Brick.target_text))
        .offset(brick_order - 1)
        .limit(1)
    )
    brick = session.exec(brick_statement).first()

    count_statement = (
        select(func.count())
        .select_from(CollectionBrick)
        .where(CollectionBrick.collection_id == collection_id)
    )
    total_count = session.exec(count_statement).one()

    return {
        "brick": brick,
        "total_bricks": total_count
    }

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
