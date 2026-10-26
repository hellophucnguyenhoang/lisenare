import re
from datetime import datetime, timezone

import numpy as np
from fastapi import status
from sqlalchemy import case
from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, exists, func, not_, select

from config import logger
from constants import MAX_BRICKS_PER_ISLAND
from database import (
    Brick,
    BrickInteraction,
    BrickMemory,
    BrickReaction,
    BrickReport,
    BrickReview,
    Island,
    LearnerSetting,
    SessionProfile,
    Tag,
    Taggable,
)
from exceptions import ErrorCode, RequestException
from redis_client import get_redis_client
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
from . import search_service
from .brick_reaction_service import get_reaction_map
from .tag_service import (
    clean_tags,
    delete_tags_for_entity,
    fetch_tags_for_entities,
    fetch_tags_for_entity,
    set_tags_for_entity,
)


def get_bricks(
    session: Session,
    creator_id: int,
    island_ids: list[int] | None = None,
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
    if island_ids:
        conditions.append(Brick.island_id.in_(island_ids))

    if status is not None:
        if status == BrickStatus.LEARNED:
            conditions.append(exists_stmt)
        elif status == BrickStatus.NOT_LEARNED:
            conditions.append(not_(exists_stmt))

    if kind is not None:
        conditions.append(Brick.kind == kind)

    if tags:
        cleaned_tags = clean_tags(tags)
        if cleaned_tags:
            tag_subquery = (
                select(Taggable.taggable_id)
                .distinct()
                .join(Tag, Taggable.tag_id == Tag.id)
                .where(
                    Taggable.taggable_type == "Brick",
                    Tag.name.in_(cleaned_tags),
                )
            )
            conditions.append(Brick.id.in_(tag_subquery))
        else:
            conditions.append(Brick.id == -1)

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
    retrieval_lang: str | None = None,
) -> list[Brick]:
    query = (
        select(Brick)
        .options(selectinload(Brick.creator))
        .where(Brick.is_private.is_(False))
    )
    if exclude_ids:
        query = query.where(Brick.id.not_in(exclude_ids))
    if retrieval_lang:
        query = query.where(Brick.target_lang == retrieval_lang)

    query = query.order_by(func.random()).limit(limit)
    return list(session.exec(query).all())


def get_recommended_bricks(
    session: Session,
    session_id: str,
    limit: int = 5,
    retrieval_lang: str | None = None,
) -> list[Brick]:
    """
    Get most relevant bricks to the profile_vector of a session_id.
    Recommend randomly for the first time.
    """
    interacted_query = select(BrickInteraction.brick_id).where(
        BrickInteraction.session_id == session_id
    )
    interacted_ids = set(session.exec(interacted_query).all())

    redis = get_redis_client()
    cache_key = f"recommended_bricks:{session_id}"
    cached_ids = {int(bid) for bid in redis.smembers(cache_key)}
    exclude_ids = list(interacted_ids | cached_ids)

    profile = session.get(SessionProfile, session_id)
    if profile:
        vector = np.frombuffer(
            profile.profile_vector, dtype=np.float64
        ).tolist()
    else:
        bricks = get_random_bricks(
            session,
            limit=limit,
            exclude_ids=exclude_ids,
            retrieval_lang=retrieval_lang,
        )
        if bricks:
            redis.sadd(cache_key, *[b.id for b in bricks if b.id is not None])
            redis.expire(cache_key, 3600)
        return bricks

    brick_ids = search_service.get_relevant_bricks(
        session,
        vector,
        limit=limit,
        exclude_ids=exclude_ids,
        lang=retrieval_lang,
    )
    if not brick_ids:
        bricks = get_random_bricks(
            session,
            limit=limit,
            exclude_ids=exclude_ids,
            retrieval_lang=retrieval_lang,
        )
        if bricks:
            redis.sadd(cache_key, *[b.id for b in bricks if b.id is not None])
            redis.expire(cache_key, 3600)
        return bricks

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
    if retrieval_lang:
        query = query.where(Brick.target_lang == retrieval_lang)

    bricks = list(session.exec(query).all())
    if bricks:
        redis.sadd(cache_key, *[b.id for b in bricks if b.id is not None])
        redis.expire(cache_key, 3600)
    return bricks


def count_bricks(
    session: Session,
    creator_id: int,
    island_ids: list[int] | None = None,
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

    if island_ids:
        conditions.append(Brick.island_id.in_(island_ids))

    if status is not None:
        if status == BrickStatus.LEARNED:
            conditions.append(exists_stmt)

        elif status == BrickStatus.NOT_LEARNED:
            conditions.append(not_(exists_stmt))

    if kind is not None:
        conditions.append(Brick.kind == kind)

    if tags:
        cleaned_tags = clean_tags(tags)
        if cleaned_tags:
            tag_subquery = (
                select(Taggable.taggable_id)
                .distinct()
                .join(Tag, Taggable.tag_id == Tag.id)
                .where(
                    Taggable.taggable_type == "Brick",
                    Tag.name.in_(cleaned_tags),
                )
            )
            conditions.append(Brick.id.in_(tag_subquery))
        else:
            conditions.append(Brick.id == -1)

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
    island = session.get(Island, brick.island_id)
    island_name = island.name if island else ""

    return BrickDetailRead.model_validate(
        brick,
        update={
            "tags": tags,
            "reaction": reaction_map.get(brick.id),
            "island_name": island_name,
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
    island_ids: list[int] | None = None,
    brick_id: int | None = None,
    retrieval_lang: str | None = None,
) -> BrickRead | None:
    if brick_id is not None:
        brick = get_brick(session, brick_id, creator_id)
        tags = fetch_tags_for_entity(session, brick.id, "Brick")
        return BrickRead.model_validate(brick, update={"tags": tags})

    if retrieval_lang is None:
        setting = session.get(LearnerSetting, creator_id)
        retrieval_lang = setting.retrieval_lang if setting else "en"

    now = datetime.now(timezone.utc)
    broken_brick_ids = session.exec(
        select(BrickReport.brick_id).where(
            BrickReport.learner_id == creator_id,
            BrickReport.status == "open",
        )
    ).all()

    def apply_filters(stmt):
        if island_ids:
            stmt = stmt.where(Brick.island_id.in_(island_ids))
        if broken_brick_ids:
            stmt = stmt.where(Brick.id.not_in(broken_brick_ids))
        if retrieval_lang:
            stmt = stmt.where(Brick.target_lang == retrieval_lang)
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
    base_new_stmt = select(Brick).where(
        Brick.creator_id == creator_id,
        Brick.id.not_in(
            select(BrickMemory.brick_id).where(
                BrickMemory.learner_id == creator_id
            )
        ),
    )
    base_new_stmt = apply_filters(base_new_stmt)

    # 1. Prefer new bricks that share tags with already learned bricks
    learned_tag_ids = select(Taggable.tag_id).where(
        Taggable.taggable_type == "Brick",
        Taggable.taggable_id.in_(
            select(BrickMemory.brick_id).where(
                BrickMemory.learner_id == creator_id
            )
        ),
    )

    shared_tag_stmt = base_new_stmt.where(
        Brick.id.in_(
            select(Taggable.taggable_id).where(
                Taggable.taggable_type == "Brick",
                Taggable.tag_id.in_(learned_tag_ids),
            )
        )
    ).order_by(func.random())

    brick = session.exec(shared_tag_stmt).first()

    # 2. Fallback: prefer shorter target_texts if no shared-tag bricks exist
    if not brick:
        fallback_stmt = base_new_stmt.order_by(
            func.length(Brick.target_text).asc(),
            func.random(),
        )
        brick = session.exec(fallback_stmt).first()

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


def count_bricks_in_island(session: Session, island_id: int) -> int:
    return (
        session.exec(
            select(func.count(Brick.id)).where(Brick.island_id == island_id)
        ).one()
        or 0
    )


def create_brick(
    session: Session,
    request_data: BrickCreateRequest,
    creator_id: int,
    target_audio_path: str,
) -> BrickRead:
    island = session.get(Island, request_data.island_id)
    if not island:
        logger.warning(
            f"Brick creation failed: Island ID {request_data.island_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Island with id {request_data.island_id} not found",
        )

    if island.creator_id != creator_id:
        logger.warning(
            f"Brick creation forbidden: creator_id: {creator_id} is not owner of island {request_data.island_id}"
        )
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} is not the creator of island {request_data.island_id}",
        )

    if count_bricks_in_island(session, island.id) >= MAX_BRICKS_PER_ISLAND:
        logger.warning(
            f"Brick creation failed: Island ID {island.id} has reached maximum limit of {MAX_BRICKS_PER_ISLAND} bricks"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Island {island.id} has reached the maximum limit of {MAX_BRICKS_PER_ISLAND} bricks",
            error_code=ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED,
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
        island_id=island.id,
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
    logger.info(
        f"Created brick ID: {brick.id} in island ID: {island.id} for creator_id: {creator_id}"
    )

    search_service.add_brick_embedding(session, brick)
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
        logger.warning(f"Brick update failed: brick_id: {brick_id} not found")
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{brick_id=} not found",
        )

    update_data = brick_update.model_dump(
        exclude_unset=True,
    )

    if brick.creator_id != creator_id:
        logger.warning(
            f"Brick update forbidden: creator_id: {creator_id} is not owner of brick_id: {brick_id}"
        )
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} is not the creator to update {brick_id=}",
        )

    new_island_id = update_data.get("island_id")
    if new_island_id is not None and new_island_id != brick.island_id:
        new_island = session.get(Island, new_island_id)
        if not new_island:
            logger.warning(
                f"Brick update failed: new island {new_island_id} not found"
            )
            raise RequestException(
                status_code=status.HTTP_404_NOT_FOUND,
                debug_message=f"Island with id {new_island_id} not found",
            )
        if new_island.creator_id != creator_id:
            logger.warning(
                f"Brick update forbidden: creator_id {creator_id} is not owner of island {new_island_id}"
            )
            raise RequestException(
                status_code=status.HTTP_403_FORBIDDEN,
                debug_message=f"{creator_id=} is not the creator of island {new_island_id}",
            )
        if count_bricks_in_island(session, new_island_id) >= MAX_BRICKS_PER_ISLAND:
            logger.warning(
                f"Brick update failed: Island ID {new_island_id} has reached maximum limit of {MAX_BRICKS_PER_ISLAND} bricks"
            )
            raise RequestException(
                status_code=status.HTTP_400_BAD_REQUEST,
                debug_message=f"Island {new_island_id} has reached the maximum limit of {MAX_BRICKS_PER_ISLAND} bricks",
                error_code=ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED,
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
    logger.info(f"Updated brick ID: {brick_id} for creator_id: {creator_id}")

    if target_audio_path:
        audio_cache_service.clear_brick_audio_cache(brick_id)

    if any(
        k in update_data for k in ("target_text", "native_text", "target_lang")
    ):
        search_service.add_brick_embedding(session, brick)

    return BrickRead.model_validate(brick, update={"tags": tags})


def delete_brick(session: Session, creator_id: int, brick_id: int) -> str:
    brick = session.get(Brick, brick_id)
    if not brick:
        logger.warning(f"Brick delete failed: brick_id: {brick_id} not found")
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{brick_id=} not found",
        )

    if brick.creator_id != creator_id:
        logger.warning(
            f"Brick delete forbidden: creator_id: {creator_id} is not owner of brick_id: {brick_id}"
        )
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} is not the creator to delete {brick_id=}",
        )

    search_service.remove_brick_embedding(session, brick)

    delete_tags_for_entity(session, brick_id, "Brick")
    session.delete(brick)
    session.commit()
    logger.info(f"Deleted brick ID: {brick_id} for creator_id: {creator_id}")

    audio_cache_service.clear_brick_audio_cache(brick_id)

    return "BRICK_DELETED"


def add_brick_from(
    session: Session,
    source_brick_id: int,
    island_id: int,
    learner_id: int,
) -> BrickRead:
    """Copy a public brick into the learner's island."""
    source = session.get(Brick, source_brick_id)
    if not source:
        logger.warning(
            f"Add brick failed: source brick {source_brick_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick {source_brick_id} not found",
        )

    # Must be public or owned by the learner
    if source.is_private and source.creator_id != learner_id:
        logger.warning(
            f"Add brick forbidden: brick {source_brick_id} is private and not owned by learner_id: {learner_id}"
        )
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message="Cannot add a private brick from another learner",
        )

    # Target island must belong to the learner
    island = session.get(Island, island_id)
    if not island or island.creator_id != learner_id:
        logger.warning(
            f"Add brick failed: target island {island_id} not found or not owned by learner_id: {learner_id}"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Island {island_id} not found",
        )

    if count_bricks_in_island(session, island_id) >= MAX_BRICKS_PER_ISLAND:
        logger.warning(
            f"Add brick failed: target island {island_id} has reached maximum limit of {MAX_BRICKS_PER_ISLAND} bricks"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Island {island_id} has reached the maximum limit of {MAX_BRICKS_PER_ISLAND} bricks",
            error_code=ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED,
        )

    # Check for duplicate
    if check_brick_exists(session, learner_id, source.target_text):
        logger.warning(
            f"Add brick conflict: duplicate target text for learner_id: {learner_id}"
        )
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
        island_id=island_id,
    )
    session.add(brick)
    session.commit()
    session.refresh(brick)
    logger.info(
        f"Copied brick ID: {source_brick_id} to new brick ID: {brick.id} "
        f"in island ID: {island_id} for learner_id: {learner_id}"
    )

    search_service.add_brick_embedding(session, brick)
    return BrickRead.model_validate(brick, update={"tags": []})


def add_bricks_from_island(
    session: Session,
    source_island_id: int,
    target_island_id: int,
    learner_id: int,
) -> dict:
    """Copy all public bricks from another learner's island."""
    source_island = session.get(Island, source_island_id)
    if not source_island:
        logger.warning(
            f"Add bricks from island failed: source island {source_island_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Source island {source_island_id} not found",
        )

    # Target island must belong to the learner
    target_island = session.get(Island, target_island_id)
    if not target_island or target_island.creator_id != learner_id:
        logger.warning(
            f"Add bricks from island failed: target island {target_island_id} not found or not owned by learner_id: {learner_id}"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Target island {target_island_id} not found",
        )

    current_count = count_bricks_in_island(session, target_island_id)
    if current_count >= MAX_BRICKS_PER_ISLAND:
        logger.warning(
            f"Add bricks from island failed: target island {target_island_id} has reached maximum limit of {MAX_BRICKS_PER_ISLAND} bricks"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Island {target_island_id} has reached the maximum limit of {MAX_BRICKS_PER_ISLAND} bricks",
            error_code=ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED,
        )

    # Get all bricks from the source island that are public
    # (or owned by the learner, if they're adding from their own island)
    stmt = select(Brick).where(Brick.island_id == source_island_id)
    if source_island.creator_id != learner_id:
        stmt = stmt.where(Brick.is_private == False)  # noqa: E712
    source_bricks = session.exec(stmt).all()

    to_add = []
    skipped = 0

    for source in source_bricks:
        if check_brick_exists(session, learner_id, source.target_text):
            skipped += 1
            continue
        to_add.append(source)

    if current_count + len(to_add) > MAX_BRICKS_PER_ISLAND:
        logger.warning(
            f"Add bricks from island failed: adding {len(to_add)} bricks to island {target_island_id} "
            f"with {current_count} bricks would exceed maximum limit of {MAX_BRICKS_PER_ISLAND}"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Island {target_island_id} cannot exceed the maximum limit of {MAX_BRICKS_PER_ISLAND} bricks",
            error_code=ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED,
        )

    for source in to_add:
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
            island_id=target_island_id,
            embedding_id=source.embedding_id,
        )
        session.add(brick)

    session.commit()
    logger.info(
        f"Copied bricks from island ID: {source_island_id} to island ID: {target_island_id} "
        f"for learner_id: {learner_id} (added: {len(to_add)}, skipped: {skipped})"
    )
    return {"added": len(to_add), "skipped": skipped}


def report_brick(
    session: Session,
    brick_id: int,
    learner_id: int,
    reason: str = "Not provided",
) -> None:
    brick = session.get(Brick, brick_id)
    if not brick:
        logger.warning(f"Report brick failed: brick_id: {brick_id} not found")
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick with id {brick_id} not found",
        )

    report = BrickReport(
        brick_id=brick_id,
        learner_id=learner_id,
        reason=reason,
    )
    session.add(report)
    session.commit()
    logger.info(
        f"Learner ID {learner_id} reported brick ID: {brick_id} (reason: '{reason}')"
    )


def forget_brick(
    session: Session,
    brick_id: int,
    learner_id: int,
) -> None:
    brick = session.get(Brick, brick_id)
    if not brick:
        logger.warning(f"Forget brick failed: brick_id: {brick_id} not found")
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick with id {brick_id} not found",
        )

    # Delete BrickMemory
    memory = session.exec(
        select(BrickMemory).where(
            BrickMemory.brick_id == brick_id,
            BrickMemory.learner_id == learner_id,
        )
    ).first()
    if memory:
        session.delete(memory)

    # Delete BrickReview rows
    reviews = session.exec(
        select(BrickReview).where(
            BrickReview.brick_id == brick_id,
            BrickReview.learner_id == learner_id,
        )
    ).all()
    for review in reviews:
        session.delete(review)

    # Delete BrickReaction
    reaction = session.get(BrickReaction, (learner_id, brick_id))
    if reaction:
        session.delete(reaction)

    # Delete BrickInteraction rows
    interactions = session.exec(
        select(BrickInteraction).where(
            BrickInteraction.brick_id == brick_id,
            BrickInteraction.learner_id == learner_id,
        )
    ).all()
    for interaction in interactions:
        session.delete(interaction)

    session.commit()
    logger.info(
        f"Reset memory and review history for brick ID: {brick_id} and learner_id: {learner_id}"
    )
