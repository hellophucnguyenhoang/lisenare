import re
from datetime import datetime, timezone

import numpy as np
from fastapi import status
from sqlalchemy import case
from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, exists, func, not_, select

from config import logger
from database import (
    Brick,
    BrickInteraction,
    BrickMemory,
    BrickReview,
    Collection,
    LearnerSetting,
    SessionProfile,
    Tag,
    Taggable,
)
from exceptions import RequestException
from schemas import (
    BrickCreate,
    BrickCreateRequest,
    BrickDetailRead,
    BrickLearnRead,
    BrickRead,
    BrickSort,
    BrickStatus,
    BrickUpdate,
)

from . import audio_cache_service
from . import context_search_service as cs_service
from .brick_reaction_service import get_reaction_map
from .tag_service import (
    delete_tags_for_entity,
    fetch_tags_for_entities,
    fetch_tags_for_entity,
    set_tags_for_entity,
)


def get_bricks(
    session: Session,
    creator_id: int,
    collection_ids: list[int] | None = None,
    status: BrickStatus | None = None,
    kind: str | None = None,
    tags: list[str] | None = None,
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

    if kind is not None:
        conditions.append(Brick.kind == kind)

    if tags:
        tag_subquery = (
            select(Taggable.taggable_id)
            .distinct()
            .join(Tag, Taggable.tag_id == Tag.id)
            .where(
                Taggable.taggable_type == "Brick",
                Tag.name.in_(tags),
            )
        )
        conditions.append(Brick.id.in_(tag_subquery))

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


def get_random_bricks(
    session: Session,
    limit: int = 5,
    exclude_ids: list[int] | None = None,
) -> list[Brick]:
    query = (
        select(Brick)
        .options(selectinload(Brick.creator))
        .where(Brick.is_private.is_(False))
    )
    if exclude_ids:
        query = query.where(Brick.id.not_in(exclude_ids))

    query = query.order_by(func.random()).limit(limit)
    return list(session.exec(query).all())


def get_recommended_bricks(
    session: Session,
    session_id: str,
    limit: int = 5,
) -> list[Brick]:
    """
    Get most relevant bricks to the profile_vector of a session_id.
    Recommend randomly for the first time.
    """
    interacted_query = select(BrickInteraction.brick_id).where(
        BrickInteraction.session_id == session_id
    )
    interacted_ids = list(session.exec(interacted_query).all())

    profile = session.get(SessionProfile, session_id)
    if profile:
        vector = np.frombuffer(
            profile.profile_vector, dtype=np.float64
        ).tolist()
    else:
        return get_random_bricks(
            session,
            limit=limit,
            exclude_ids=interacted_ids,
        )

    brick_ids = cs_service.search_service.get_relevant_bricks(
        vector,
        limit=limit,
        exclude_ids=interacted_ids,
    )
    if not brick_ids:
        return get_random_bricks(
            session,
            limit=limit,
            exclude_ids=interacted_ids,
        )

    # Preserving the order of brick_ids in the provided relevance order
    order_preserved = case(
        {id_: index for index, id_ in enumerate(brick_ids)},
        value=Brick.id,
    )

    query = (
        select(Brick)
        .where(Brick.id.in_(brick_ids), Brick.is_private.is_(False))
        .options(selectinload(Brick.creator))
        .order_by(order_preserved)
    )

    return list(session.exec(query).all())


def count_bricks(
    session: Session,
    creator_id: int,
    collection_ids: list[int] | None = None,
    status: BrickStatus | None = None,
    kind: str | None = None,
    tags: list[str] | None = None,
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

    if kind is not None:
        conditions.append(Brick.kind == kind)

    if tags:
        tag_subquery = (
            select(Taggable.taggable_id)
            .distinct()
            .join(Tag, Taggable.tag_id == Tag.id)
            .where(
                Taggable.taggable_type == "Brick",
                Tag.name.in_(tags),
            )
        )
        conditions.append(Brick.id.in_(tag_subquery))

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
            debug_message=f"Brick {brick_id} not found for creator {creator_id}",
        )
    return brick


def get_brick_detail(
    session: Session,
    brick_id: int,
    learner_id: int,
) -> BrickDetailRead:
    brick = session.get(Brick, brick_id)
    if not brick:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick {brick_id} not found",
        )

    if brick.is_private and brick.creator_id != learner_id:
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message="Cannot view a private brick from another learner",
        )

    tags = fetch_tags_for_entity(session, brick.id, "Brick")
    reaction_map = get_reaction_map(session, [brick.id], learner_id)
    collection = session.get(Collection, brick.collection_id)
    collection_name = collection.name if collection else ""

    return BrickDetailRead.model_validate(
        brick,
        update={
            "tags": tags,
            "reaction": reaction_map.get(brick.id),
            "collection_name": collection_name,
        },
    )


def get_brick_by_audio_path(session: Session, audio_path: str) -> Brick:
    stmt = select(Brick).where(Brick.target_audio_path == audio_path)
    brick = session.exec(stmt).first()
    if not brick:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick with audio path '{audio_path}' not found",
        )
    return brick


def get_next_brick(
    session: Session,
    creator_id: int,
    collection_ids: list[int] | None = None,
    brick_id: int | None = None,
    practice_lang: str | None = None,
) -> BrickRead | None:
    if brick_id is not None:
        brick = get_brick(session, brick_id, creator_id)
        tags = fetch_tags_for_entity(session, brick.id, "Brick")
        return BrickRead.model_validate(brick, update={"tags": tags})

    if practice_lang is None:
        setting = session.get(LearnerSetting, creator_id)
        practice_lang = setting.practice_lang if setting else "en"

    now = datetime.now(timezone.utc)
    broken_brick_ids = []  # TODO: Get reported brick id

    def apply_filters(stmt):
        if collection_ids:
            stmt = stmt.where(Brick.collection_id.in_(collection_ids))
        if broken_brick_ids:
            stmt = stmt.where(Brick.id.not_in(broken_brick_ids))
        if practice_lang:
            stmt = stmt.where(Brick.target_lang == practice_lang)
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
        logger.info("FSRS Case 1: Get the least overdue card")
        tags = fetch_tags_for_entity(session, brick.id, "Brick")
        return BrickRead.model_validate(brick, update={"tags": tags})

    logger.info("FSRS Case 2: Get a new card")
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
    brick = session.exec(new_stmt).first()
    if brick:
        tags = fetch_tags_for_entity(session, brick.id, "Brick")
        return BrickRead.model_validate(brick, update={"tags": tags})
    return None


def check_brick_exists(
    session: Session, creator_id: int, target_text: str
) -> bool:
    # \w matches Unicode word characters (letters, digits, underscores) globally
    cleaned_target = re.sub(r"[^\w]", "", target_text).lower()

    stmt = select(Brick).where(
        Brick.creator_id == creator_id,
        func.lower(func.regexp_replace(Brick.target_text, r"[^\w]", "", "g"))
        == cleaned_target,
    )
    result = session.exec(stmt).first()
    return result is not None


def create_brick(
    session: Session,
    request_data: BrickCreateRequest,
    creator_id: int,
    target_audio_path: str,
) -> BrickRead:
    collection = session.get(Collection, request_data.collection_id)
    if not collection:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Collection with id {request_data.collection_id} not found",
        )

    if collection.creator_id != creator_id:
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} is not the creator of collection {request_data.collection_id}",
        )

    brick_create = BrickCreate(
        native_text=request_data.native_text,
        target_text=request_data.target_text,
        target_lang=request_data.target_lang,
        target_pron=request_data.target_pron,
        context=request_data.context,
        kind=request_data.kind,
        target_audio_path=target_audio_path,
        is_private=request_data.is_private,
        creator_id=creator_id,
        collection_id=collection.id,
    )
    brick = Brick.model_validate(brick_create)
    session.add(brick)
    session.flush()

    tags: list[str] = []
    if request_data.tags:
        tags = set_tags_for_entity(
            session=session,
            entity_id=brick.id,
            entity_type="Brick",
            tag_names=request_data.tags,
            creator_id=creator_id,
        )

    session.commit()
    session.refresh(brick)

    cs_service.add_item_to_vector_store(
        search_service=cs_service.search_service,
        item=brick,
        store_key="bricks",
        text_getter=lambda b: f"{b.target_text} {b.native_text}",
        metadata_getter=lambda b: {
            "brick_id": b.id,
            "target_text": b.target_text,
            "native_text": b.native_text,
            "target_lang": b.target_lang,
        },
        id_prefix="Brick",
    )
    return BrickRead.model_validate(brick, update={"tags": tags})


def update_brick(
    session: Session,
    brick_id: int,
    brick_update: BrickUpdate,
    creator_id: int,
    target_audio_path: str | None = None,
) -> BrickRead:
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

    tags_to_update = update_data.pop("tags", None)

    # Update top-level brick fields
    for key, value in update_data.items():
        setattr(brick, key, value)

    # Update audio if a new file was uploaded
    if target_audio_path:
        brick.target_audio_path = target_audio_path

    brick.last_edit_at = datetime.now(timezone.utc)
    session.add(brick)

    if tags_to_update is not None:
        tags = set_tags_for_entity(
            session=session,
            entity_id=brick.id,
            entity_type="Brick",
            tag_names=tags_to_update,
            creator_id=creator_id,
        )
    else:
        tags = fetch_tags_for_entity(session, brick.id, "Brick")

    session.commit()
    session.refresh(brick)

    if target_audio_path:
        audio_cache_service.clear_brick_audio_cache(brick_id)

    return BrickRead.model_validate(brick, update={"tags": tags})


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

    cs_service.delete_item_from_vector_store(
        search_service=cs_service.search_service,
        item_id=brick_id,
        store_key="bricks",
        id_prefix="Brick",
    )

    delete_tags_for_entity(session, brick_id, "Brick")
    session.delete(brick)
    session.commit()

    audio_cache_service.clear_brick_audio_cache(brick_id)

    return "BRICK_DELETED"


def add_brick_from(
    session: Session,
    source_brick_id: int,
    collection_id: int,
    learner_id: int,
) -> BrickRead:
    """Copy a public brick into the learner's collection."""
    source = session.get(Brick, source_brick_id)
    if not source:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick {source_brick_id} not found",
        )

    # Must be public or owned by the learner
    if source.is_private and source.creator_id != learner_id:
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message="Cannot add a private brick from another learner",
        )

    # Target collection must belong to the learner
    collection = session.get(Collection, collection_id)
    if not collection or collection.creator_id != learner_id:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Collection {collection_id} not found",
        )

    # Check for duplicate
    if check_brick_exists(session, learner_id, source.target_text):
        raise RequestException(
            status_code=status.HTTP_409_CONFLICT,
            debug_message="You already have a brick with this target text",
        )

    brick = Brick(
        native_text=source.native_text,
        target_text=source.target_text,
        target_audio_path=source.target_audio_path,
        target_lang=source.target_lang,
        target_pron=source.target_pron,
        context=source.context,
        kind=source.kind,
        is_private=True,
        creator_id=learner_id,
        collection_id=collection_id,
    )
    session.add(brick)
    session.commit()
    session.refresh(brick)

    cs_service.add_item_to_vector_store(
        search_service=cs_service.search_service,
        item=brick,
        store_key="bricks",
        text_getter=lambda b: f"{b.target_text} {b.native_text}",
        metadata_getter=lambda b: {
            "brick_id": b.id,
            "target_text": b.target_text,
            "native_text": b.native_text,
            "target_lang": b.target_lang,
        },
        id_prefix="Brick",
    )
    return BrickRead.model_validate(brick, update={"tags": []})


def add_bricks_from_collection(
    session: Session,
    source_collection_id: int,
    target_collection_id: int,
    learner_id: int,
) -> dict:
    """Copy all public bricks from another learner's collection."""
    source_collection = session.get(Collection, source_collection_id)
    if not source_collection:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Source collection {source_collection_id} not found",
        )

    # Target collection must belong to the learner
    target_collection = session.get(Collection, target_collection_id)
    if not target_collection or target_collection.creator_id != learner_id:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Target collection {target_collection_id} not found",
        )

    # Get all bricks from the source collection that are public
    # (or owned by the learner, if they're adding from their own collection)
    stmt = select(Brick).where(Brick.collection_id == source_collection_id)
    if source_collection.creator_id != learner_id:
        stmt = stmt.where(Brick.is_private == False)  # noqa: E712
    source_bricks = session.exec(stmt).all()

    added = 0
    skipped = 0

    for source in source_bricks:
        if check_brick_exists(session, learner_id, source.target_text):
            skipped += 1
            continue

        brick = Brick(
            native_text=source.native_text,
            target_text=source.target_text,
            target_audio_path=source.target_audio_path,
            target_lang=source.target_lang,
            target_pron=source.target_pron,
            context=source.context,
            kind=source.kind,
            is_private=True,
            creator_id=learner_id,
            collection_id=target_collection_id,
        )
        session.add(brick)
        added += 1

    session.commit()
    return {"added": added, "skipped": skipped}
