from fastapi import HTTPException, status
from sqlmodel import Session, select, delete, func
from pathlib import Path
from datetime import datetime, timezone

from app.database import (
    Brick,
    CollectionBrick,
    BrickMetadata,
    LearningCard,
    BrickOverride,
)
from app.config import settings
from app.schemas import BrickUpdate, BrickCreate, UnitType
from . import brick_override_service, collection_service


def get_brick(session: Session, id: int) -> Brick:
    brick = session.exec(select(Brick).where(Brick.id == id)).first()
    if not brick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Brick not found"
        )
    return brick


def iter_audio_file(filename: str):
    base_dir = Path(settings.brick_folder)
    file_path = (base_dir / filename).resolve()
    with open(file_path, "rb") as audio_file:
        yield from audio_file


async def get_audio_file(filename: str):
    base_dir = Path(settings.brick_folder)
    file_path = (base_dir / filename).resolve()
    with open(file_path, "rb") as audio_file:
        return audio_file.read()


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
            BrickMetadata.unit_type == UnitType.sentence,
        )
    )

    if collection_ids:
        statement = statement.where(
            CollectionBrick.collection_id.in_(collection_ids)
        )

    statement = statement.order_by(func.random()).limit(1)

    return session.exec(statement).first()


def get_broken_filenames() -> set[str]:
    REPORT_FILE = Path(settings.broken_report_file)
    if not REPORT_FILE.exists():
        return set()
    # Read and split by "|", taking the first part (filename)
    with REPORT_FILE.open("r") as f:
        return {line.split("|")[0] for line in f if "|" in line}


def get_brick_fsrs(
    session: Session,
    learner_id: int,
    collection_ids: list[int] | None = None,
) -> Brick | None:
    now = datetime.now(timezone.utc)
    broken_files = get_broken_filenames()

    def apply_filters(stmt):
        if collection_ids:
            stmt = stmt.where(
                CollectionBrick.collection_id.in_(collection_ids)
            )
        if broken_files:
            stmt = stmt.where(~Brick.target_audio_uri.in_(broken_files))
        return stmt

    def resolve_override(result):
        if not result:
            return None
        brick, override_native = result
        if override_native:
            brick.native_text = override_native
        return brick

    # Common override join condition
    override_join = (BrickOverride.brick_id == Brick.id) & (
        BrickOverride.learner_id == learner_id
    )

    # 1. Due cards
    due_stmt = (
        select(Brick, BrickOverride.native_text)
        .join(LearningCard, LearningCard.brick_id == Brick.id)
        .join(CollectionBrick, CollectionBrick.brick_id == Brick.id)
        .join(BrickMetadata)
        .outerjoin(BrickOverride, override_join)
        .where(
            LearningCard.learner_id == learner_id,
            LearningCard.due <= now,
            BrickMetadata.unit_type == UnitType.sentence,
        )
        .order_by(LearningCard.due)
        .limit(1)
    )

    due_stmt = apply_filters(due_stmt)
    result = session.exec(due_stmt).first()
    brick = resolve_override(result)
    if brick:
        return brick

    # 2. New unseen bricks
    pending_bricks_subq = collection_service.get_pending_bricks_subquery(
        learner_id
    )

    new_stmt = (
        select(Brick, BrickOverride.native_text)
        .join(pending_bricks_subq, pending_bricks_subq.c.id == Brick.id)
        .join(CollectionBrick)
        .join(BrickMetadata)
        .outerjoin(BrickOverride, override_join)
        .where(
            BrickMetadata.unit_type == UnitType.sentence,
            ~Brick.id.in_(
                select(LearningCard.brick_id).where(
                    LearningCard.learner_id == learner_id
                )
            ),
        )
        .order_by(func.length(Brick.target_text))
        .limit(1)
    )

    new_stmt = apply_filters(new_stmt)
    result = session.exec(new_stmt).first()
    return resolve_override(result)


def get_brick_in_collection_learn(
    session: Session,
    learner_id: int,
    collection_id: int,
    brick_order: int = 1,
) -> dict | None:

    pending_bricks_subq = collection_service.get_pending_bricks_subquery(
        learner_id
    )

    override_join = (BrickOverride.brick_id == Brick.id) & (
        BrickOverride.learner_id == learner_id
    )

    stmt = (
        select(Brick, BrickOverride.native_text)
        .join(pending_bricks_subq, pending_bricks_subq.c.id == Brick.id)
        .join(CollectionBrick, CollectionBrick.brick_id == Brick.id)
        .outerjoin(BrickOverride, override_join)
        .where(CollectionBrick.collection_id == collection_id)
        .order_by(func.length(Brick.target_text))
        .offset(brick_order - 1)
        .limit(1)
    )
    result = session.exec(stmt).first()
    if not result:
        return None

    brick, override_native = result
    if override_native:
        brick.native_text = override_native

    # Count only learning bricks inside this collection
    count_stmt = (
        select(func.count())
        .select_from(CollectionBrick)
        .join(
            pending_bricks_subq,
            pending_bricks_subq.c.id == CollectionBrick.brick_id,
        )
        .where(CollectionBrick.collection_id == collection_id)
    )
    total_bricks = session.exec(count_stmt).one()
    return {
        "brick": brick,
        "total_bricks": total_bricks,
    }


def update_brick(
    session: Session,
    brick_id: int,
    brick_update: BrickUpdate,
    learner_id: int,
) -> Brick:

    brick = session.get(Brick, brick_id)
    if not brick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brick not found",
        )

    # Case 1: Author edits original
    if brick.creator_id == learner_id:

        data = brick_update.model_dump(
            exclude_unset=True,
            exclude={"collection_ids"},
        )

        for key, value in data.items():
            setattr(brick, key, value)

        if brick_update.collection_ids is not None:
            session.exec(
                delete(CollectionBrick).where(
                    CollectionBrick.brick_id == brick_id
                )
            )

            for collection_id in brick_update.collection_ids:
                session.add(
                    CollectionBrick(
                        collection_id=collection_id,
                        brick_id=brick_id,
                    )
                )

        brick.last_edit_at = datetime.now(timezone.utc)

        session.add(brick)
        session.commit()
        session.refresh(brick)
        return brick

    # Case 2: Non-author edits → save override
    else:
        override = brick_override_service.save_override_for_brick(
            session=session,
            learner_id=learner_id,
            brick_id=brick_id,
            native_text=brick_update.native_text,
        )
        brick.native_text = override.native_text
        return brick


def create_brick(session: Session, brick_create: BrickCreate) -> Brick:
    db_brick = Brick.model_validate(brick_create)
    session.add(db_brick)

    collection = collection_service.get_or_create_collection(
        session,
        brick_create.collection_name,
        brick_create.group_name,
        brick_create.creator_id,
    )

    collection.bricks.append(db_brick)

    session.commit()
    session.refresh(db_brick)

    collection_service.update_collection_difficulty(session, collection.id)

    return db_brick
