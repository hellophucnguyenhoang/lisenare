from collections import defaultdict
from datetime import datetime, timezone

from fastapi import status
from sqlmodel import Session, col, func, select

from config import logger
from database import Brick, BrickMemory, BrickReview, Island
from exceptions import ErrorCode, RequestException
from schemas import (
    AddIslandResult,
    BrickExport,
    BrickMemoryExport,
    BrickReviewExport,
    IslandCreate,
    IslandUpdate,
)

from .brick_service import check_brick_exists
from .tag_service import (
    delete_tags_for_entity,
    fetch_tags_for_entities,
    fetch_tags_for_entity,
    set_tags_for_entity,
)


def create_island(
    session: Session,
    creator_id: int,
    island_create: IslandCreate,
) -> tuple[Island, list[str]]:
    cleaned_name = island_create.name.strip()
    if not cleaned_name:
        logger.warning(
            f"Failed to create island: empty name for creator_id: {creator_id}"
        )
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message="Island name cannot be empty",
        )

    existing_stmt = select(Island).where(
        Island.creator_id == creator_id,
        Island.name == cleaned_name,
    )
    if session.exec(existing_stmt).first():
        logger.warning(
            f"Failed to create island: '{cleaned_name}' already exists for creator_id: {creator_id}"
        )
        raise RequestException(
            status_code=status.HTTP_409_CONFLICT,
            debug_message=f"Island named '{cleaned_name}' already exists for this learner",
            error_code=ErrorCode.COLLECTION_ALREADY_EXISTS,
        )

    island = Island(
        name=cleaned_name,
        description=island_create.description,
        creator_id=creator_id,
    )
    session.add(island)
    session.flush()

    tags: list[str] = []
    if island_create.tags:
        tags = set_tags_for_entity(
            session=session,
            entity_id=island.id,
            entity_type="Island",
            tag_names=island_create.tags,
            creator_id=creator_id,
        )

    session.commit()
    session.refresh(island)
    logger.info(
        f"Created island '{island.name}' (ID: {island.id}) for creator_id: {creator_id}"
    )

    return island, tags


def get_or_create_island(
    session: Session, island_name: str, creator_id: int
) -> Island:
    stmt = select(Island).where(
        Island.name == island_name, Island.creator_id == creator_id
    )
    island = session.exec(stmt).first()

    if not island:
        island = Island(
            name=island_name,
            creator_id=creator_id,
        )
        session.add(island)
        session.commit()
        session.refresh(island)

    return island


def get_islands(
    session: Session, creator_id: int
) -> list[tuple[Island, int, int, list]]:
    # Get all islands for this creator
    islands = session.exec(
        select(Island).where(Island.creator_id == creator_id)
    ).all()

    if not islands:
        return []

    island_ids = [c.id for c in islands]

    # Get total brick counts per island
    brick_counts = dict(
        session.exec(
            select(Brick.island_id, func.count(Brick.id))
            .where(Brick.island_id.in_(island_ids))
            .group_by(Brick.island_id)
        ).all()
    )

    # Get learned brick counts per island
    learned_counts = dict(
        session.exec(
            select(Brick.island_id, func.count(Brick.id))
            .join(BrickReview, BrickReview.brick_id == Brick.id)
            .where(
                Brick.island_id.in_(island_ids),
                BrickReview.learner_id == creator_id,
            )
            .group_by(Brick.island_id)
        ).all()
    )

    island_tags = fetch_tags_for_entities(session, island_ids, "Island")

    # Merge everything into a clear, flat tuple list
    return [
        (
            col,
            brick_counts.get(col.id, 0),
            learned_counts.get(col.id, 0),
            island_tags[col.id],
        )
        for col in islands
    ]


def delete_island(
    session: Session,
    creator_id: int,
    island_id: int,
) -> str:
    island = session.get(Island, island_id)
    if not island:
        logger.warning(
            f"Island delete failed: island_id: {island_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{island_id=} not found",
        )

    if island.creator_id != creator_id:
        logger.warning(
            f"Island delete forbidden: creator_id: {creator_id} is not creator of island_id: {island_id}"
        )
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} is not the creator to delete {island_id=}",
        )

    delete_tags_for_entity(session, island_id, "Island")
    session.delete(island)
    session.commit()
    logger.info(f"Deleted island ID: {island_id} for creator_id: {creator_id}")

    return "COLLECTION_DELETED"


def update_island(
    session: Session,
    creator_id: int,
    island_id: int,
    island_update: IslandUpdate,
) -> tuple[Island, int, int, list[str]]:
    island = session.get(Island, island_id)
    if not island:
        logger.warning(
            f"Island update failed: island_id: {island_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{island_id=} not found",
        )

    if island.creator_id != creator_id:
        logger.warning(
            f"Island update forbidden: creator_id: {creator_id} is not creator of island_id: {island_id}"
        )
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} not the creator to edit {island_id=}",
        )

    if island_update.name is not None:
        cleaned_name = island_update.name.strip()
        if not cleaned_name:
            logger.warning(
                f"Island update failed: empty new name for island_id: {island_id}"
            )
            raise RequestException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                debug_message="New island name is empty",
            )

        existing_stmt = select(Island).where(
            Island.creator_id == creator_id,
            Island.name == cleaned_name,
            Island.id != island_id,
        )
        if session.exec(existing_stmt).first():
            logger.warning(
                f"Island update conflict: name '{cleaned_name}' already exists for creator_id: {creator_id}"
            )
            raise RequestException(
                status_code=status.HTTP_409_CONFLICT,
                debug_message=f"Island named '{cleaned_name}' already exists for this learner",
                error_code=ErrorCode.COLLECTION_ALREADY_EXISTS,
            )
        island.name = cleaned_name

    if island_update.description is not None:
        island.description = island_update.description

    session.add(island)

    if island_update.tags is not None:
        tags = set_tags_for_entity(
            session=session,
            entity_id=island.id,
            entity_type="Island",
            tag_names=island_update.tags,
            creator_id=creator_id,
        )
    else:
        tags = fetch_tags_for_entity(session, island.id, "Island")

    session.commit()
    session.refresh(island)

    brick_count = (
        session.exec(
            select(func.count(Brick.id)).where(Brick.island_id == island.id)
        ).one()
        or 0
    )

    learned_count = (
        session.exec(
            select(func.count(Brick.id))
            .join(BrickReview, BrickReview.brick_id == Brick.id)
            .where(
                Brick.island_id == island.id,
                BrickReview.learner_id == creator_id,
            )
        ).one()
        or 0
    )

    logger.info(f"Updated island ID: {island_id} for creator_id: {creator_id}")
    return island, brick_count, learned_count, tags


def rename_island(
    session: Session,
    creator_id: int,
    island_id: int,
    new_name: str,
) -> Island:
    col, _, _, _ = update_island(
        session=session,
        creator_id=creator_id,
        island_id=island_id,
        island_update=IslandUpdate(name=new_name),
    )
    return col


def export_island(
    session: Session,
    island_id: int,
    learner_id: int,
    include_memory: bool = True,
    include_review_history: bool = True,
) -> list[BrickExport]:
    island = session.get(Island, island_id)
    if not island:
        logger.warning(
            f"Island export failed: island_id: {island_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Island {island_id} not found",
        )

    stmt = select(Brick).where(Brick.island_id == island_id)
    if island.creator_id != learner_id:
        stmt = stmt.where(Brick.is_private == False)  # noqa: E712

    bricks = session.exec(stmt).all()
    if not bricks:
        logger.info(
            f"Exported empty island ID: {island_id} for learner_id: {learner_id}"
        )
        return []

    brick_ids = [b.id for b in bricks if b.id is not None]
    tags_map = fetch_tags_for_entities(session, brick_ids, "Brick")

    memories_map: dict[int, BrickMemory] = {}
    if include_memory and brick_ids:
        memories = session.exec(
            select(BrickMemory).where(
                BrickMemory.learner_id == learner_id,
                col(BrickMemory.brick_id).in_(brick_ids),
            )
        ).all()
        memories_map = {m.brick_id: m for m in memories}

    reviews_map: dict[int, list[BrickReview]] = defaultdict(list)
    if include_review_history and brick_ids:
        reviews = session.exec(
            select(BrickReview)
            .where(
                BrickReview.learner_id == learner_id,
                col(BrickReview.brick_id).in_(brick_ids),
            )
            .order_by(BrickReview.reviewed_at.asc())
        ).all()
        for r in reviews:
            reviews_map[r.brick_id].append(r)

    result = []
    for b in bricks:
        memory_export = None
        if include_memory and b.id in memories_map:
            m = memories_map[b.id]
            memory_export = BrickMemoryExport(
                fsrs_card_dict=m.fsrs_card_dict,
                due=m.due,
                created_at=m.created_at,
            )

        review_history_export = None
        if include_review_history:
            review_history_export = [
                BrickReviewExport(
                    reviewed_at=r.reviewed_at,
                    first_score=r.first_score,
                    is_answer_revealed=r.is_answer_revealed,
                    fsrs_rating=r.fsrs_rating,
                    fsrs_log_dict=r.fsrs_log_dict,
                    learner_target_text=r.learner_target_text,
                    learner_target_audio_path=r.learner_target_audio_path,
                )
                for r in reviews_map.get(b.id, [])
            ]

        result.append(
            BrickExport(
                native_text=b.native_text,
                target_text=b.target_text,
                target_audio_path=b.target_audio_path,
                target_lang=b.target_lang,
                target_pron=b.target_pron,
                context=b.context,
                kind=b.kind,
                tags=tags_map.get(b.id, []),
                is_private=b.is_private,
                memory=memory_export,
                review_history=review_history_export,
            )
        )

    logger.info(
        f"Exported island ID: {island_id} ({len(result)} bricks) for learner_id: {learner_id}"
    )
    return result


def import_island(
    session: Session,
    island_id: int,
    learner_id: int,
    bricks: list[BrickExport],
) -> AddIslandResult:
    island = session.get(Island, island_id)
    if not island:
        logger.warning(
            f"Island import failed: island_id: {island_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Island {island_id} not found",
        )

    if island.creator_id != learner_id:
        logger.warning(
            f"Island import forbidden: learner_id: {learner_id} is not creator of island_id: {island_id}"
        )
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{learner_id=} is not the creator of island {island_id}",
        )

    added = 0
    skipped = 0
    seen_in_batch: set[str] = set()

    for item in bricks:
        norm_text = item.target_text.strip().lower()
        if norm_text in seen_in_batch or check_brick_exists(
            session,
            learner_id,
            item.target_text,
        ):
            skipped += 1
            continue

        seen_in_batch.add(norm_text)
        brick = Brick(
            native_text=item.native_text,
            target_text=item.target_text,
            target_audio_path=item.target_audio_path,
            target_lang=item.target_lang,
            target_pron=item.target_pron,
            context=item.context,
            kind=item.kind,
            is_private=item.is_private,
            creator_id=learner_id,
            island_id=island_id,
        )
        session.add(brick)
        session.flush()

        if item.tags:
            set_tags_for_entity(
                session=session,
                entity_id=brick.id,
                entity_type="Brick",
                tag_names=item.tags,
                creator_id=learner_id,
            )

        if item.memory:
            db_memory = BrickMemory(
                learner_id=learner_id,
                brick_id=brick.id,
                fsrs_card_dict=item.memory.fsrs_card_dict,
                due=item.memory.due,
                created_at=item.memory.created_at
                or datetime.now(timezone.utc),
            )
            session.add(db_memory)

        if item.review_history:
            for r in item.review_history:
                db_review = BrickReview(
                    learner_id=learner_id,
                    brick_id=brick.id,
                    reviewed_at=r.reviewed_at,
                    first_score=r.first_score,
                    is_answer_revealed=r.is_answer_revealed,
                    fsrs_rating=r.fsrs_rating,
                    fsrs_log_dict=r.fsrs_log_dict,
                    learner_target_text=r.learner_target_text,
                    learner_target_audio_path=r.learner_target_audio_path,
                )
                session.add(db_review)

        added += 1

    session.commit()
    logger.info(
        f"Imported island ID: {island_id} for learner_id: {learner_id} (added: {added}, skipped: {skipped})"
    )
    return AddIslandResult(added=added, skipped=skipped)
