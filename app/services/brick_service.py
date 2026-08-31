from datetime import datetime, timezone

from fastapi import status
from sqlmodel import Session, and_, exists, func, not_, select

from app.database import Brick, BrickMemory, BrickReview
from app.exceptions import RequestException
from app.schemas import (
    BrickCreate,
    BrickCreateRequest,
    BrickLearnRead,
    BrickSort,
    BrickStatus,
    BrickUpdate,
)

from . import collection_service
from . import context_search_service as search_service
from .tag_service import fetch_tags_for_entities


def get_bricks(
    session: Session,
    creator_id: int,
    collection_ids: list[int] | None = None,
    status: BrickStatus | None = None,
    sort_by: BrickSort = BrickSort.NEWEST,
    offset: int = 0,
    limit: int = 20,
) -> list[BrickLearnRead]:
    exists_stmt = exists().where(
        and_(
            BrickReview.brick_id == Brick.id,
            BrickReview.learner_id == creator_id,
        )
    )

    learned_column = exists_stmt.label("learned")
    stmt = select(Brick, learned_column).where(Brick.creator_id == creator_id)

    conditions = []
    if collection_ids:
        conditions.append(Brick.collection_id.in_(collection_ids))

    if status is not None:
        if status == BrickStatus.LEARNED:
            conditions.append(exists_stmt)
        elif status == BrickStatus.NOT_LEARNED:
            conditions.append(not_(exists_stmt))

    if conditions:
        stmt = stmt.where(*conditions)

    if sort_by == BrickSort.NEWEST:
        stmt = stmt.order_by(Brick.last_edit_at.desc())
    elif sort_by == BrickSort.AZ:
        stmt = stmt.order_by(Brick.target_text.asc())
    elif sort_by == BrickSort.ZA:
        stmt = stmt.order_by(Brick.target_text.desc())

    stmt = stmt.offset(offset).limit(limit)
    results = session.exec(stmt).all()

    bricks = []
    for brick, learned in results:
        read_schema = BrickLearnRead.model_validate(
            brick, update={"learned": bool(learned)}
        )
        bricks.append(read_schema)

    # Get tags per brick
    brick_ids = [brick.id for brick in bricks]
    brick_tags = fetch_tags_for_entities(session, brick_ids, "Brick")

    for brick in bricks:
        brick.tags = brick_tags.get(brick.id, [])

    return bricks


def count_bricks(
    session: Session,
    creator_id: int,
    collection_ids: list[int] | None = None,
    status: BrickStatus | None = None,
) -> int:
    exists_stmt = exists().where(
        and_(
            BrickReview.brick_id == Brick.id,
            BrickReview.learner_id == creator_id,
        )
    )

    stmt = select(func.count(Brick.id)).where(Brick.creator_id == creator_id)
    conditions = []

    if collection_ids:
        conditions.append(Brick.collection_id.in_(collection_ids))

    if status is not None:
        if status == BrickStatus.LEARNED:
            conditions.append(exists_stmt)

        elif status == BrickStatus.NOT_LEARNED:
            conditions.append(not_(exists_stmt))

    if conditions:
        stmt = stmt.where(*conditions)

    total_count = session.exec(stmt).one()
    return total_count


def get_brick(session: Session, brick_id: int, creator_id: int) -> Brick:
    stmt = select(Brick).where(
        Brick.id == brick_id, Brick.creator_id == creator_id
    )
    brick = session.exec(stmt).first()
    if not brick:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick with ID {brick_id} not found",
        )
    return brick


def get_next_brick(
    session: Session,
    creator_id: int,
    collection_ids: list[int] | None = None,
) -> Brick | None:
    now = datetime.now(timezone.utc)
    broken_brick_ids = []  # TODO: Get reported brick id

    def apply_filters(stmt):
        if collection_ids:
            stmt = stmt.where(Brick.collection_id.in_(collection_ids))
        if broken_brick_ids:
            stmt = stmt.where(Brick.id.not_in(broken_brick_ids))
        return stmt

    due_stmt = (
        select(Brick)
        .join(BrickMemory, BrickMemory.brick_id == Brick.id)
        .where(
            Brick.creator_id == creator_id,
            BrickMemory.learner_id == creator_id,
            BrickMemory.due <= now,
        )
        .order_by(BrickMemory.due.desc())
    )

    due_stmt = apply_filters(due_stmt)
    brick = session.exec(due_stmt).first()
    if brick:
        print("FSRS Case 1: Get the least overdue card")
        return brick

    print("FSRS Case 2: Get a new card")
    new_stmt = (
        select(Brick)
        .where(
            Brick.creator_id == creator_id,
            Brick.id.not_in(
                select(BrickMemory.brick_id).where(
                    BrickMemory.learner_id == creator_id
                )
            ),
        )
        .order_by(func.random())
    )

    new_stmt = apply_filters(new_stmt)
    return session.exec(new_stmt).first()


def check_target_text_exists(
    session: Session, creator_id: int, target_text: str
) -> bool:
    stmt = select(Brick).where(
        Brick.creator_id == creator_id,
        func.lower(func.trim(Brick.target_text))
        == target_text.strip().lower(),
    )
    result = session.exec(stmt).first()
    return result is not None


def create_brick(
    session: Session,
    request_data: BrickCreateRequest,
    creator_id: int,
    target_audio_path: str,
) -> Brick:
    collection = collection_service.get_or_create_collection(
        session,
        request_data.collection_name,
        creator_id,
    )

    brick_create = BrickCreate(
        native_text=request_data.native_text,
        target_text=request_data.target_text,
        target_audio_path=target_audio_path,  # e.g. "brick-audios/learner_1_audio.m4a"
        is_private=request_data.is_private,
        creator_id=creator_id,
        collection_id=collection.id,
    )
    brick = Brick.model_validate(brick_create)
    session.add(brick)
    session.commit()
    session.refresh(brick)

    search_service.add_item_to_vector_store(
        search_service=search_service.context_search_service,
        item=brick,
        store_key="bricks",
        text_getter=lambda b: f"{b.target_text} {b.native_text}",
        metadata_getter=lambda b: {
            "brick_id": b.id,
            "target_text": b.target_text,
            "native_text": b.native_text,
        },
        id_prefix="Brick",
    )
    return brick


def update_brick(
    session: Session,
    brick_id: int,
    brick_update: BrickUpdate,
    creator_id: int,
    target_audio_path: str | None = None,
) -> Brick:
    stmt = select(Brick).where(Brick.id == brick_id)
    brick = session.exec(stmt).first()
    if not brick:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{brick_id=} not found",
        )

    update_data = brick_update.model_dump(
        exclude_unset=True,
    )

    if brick.creator_id != creator_id:
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} is not the creator to update {brick_id=}",
        )

    # Update top-level brick fields
    for key, value in update_data.items():
        setattr(brick, key, value)

    # Update audio if a new file was uploaded
    if target_audio_path:
        brick.target_audio_path = target_audio_path

    brick.last_edit_at = datetime.now(timezone.utc)
    session.add(brick)
    session.commit()
    session.refresh(brick)
    return brick


def delete_brick(session: Session, creator_id: int, brick_id: int) -> str:
    brick = session.get(Brick, brick_id)
    if not brick:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{brick_id=} not found",
        )

    if brick.creator_id != creator_id:
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} is not the creator to delete {brick_id=}",
        )

    search_service.delete_item_from_vector_store(
        search_service=search_service.context_search_service,
        item_id=brick_id,
        store_key="bricks",
        id_prefix="Brick",
    )

    session.delete(brick)
    session.commit()

    return "BRICK_DELETED"
