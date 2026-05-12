from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.database import Brick, BrickOverride, Collection
from utils import text_utils

from . import collection_service


def save_override_for_brick(
    session: Session,
    learner_id: int,
    brick_id: int,
) -> BrickOverride:
    brick = session.get(Brick, brick_id)
    if not brick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brick not found",
        )

    override = session.get(
        BrickOverride,
        (learner_id, brick_id),
    )
    if not override:
        difficulty_score = text_utils.log_frequency(brick.target_text)

        # Create learner-owned collection copy
        collection = Collection(
            name=brick.collection.name,
            group_name=brick.collection.group_name,
            creator_id=learner_id,
            difficulty_score=difficulty_score,
        )
        session.add(collection)

        # Flush so collection.id is generated
        session.flush()

        override = BrickOverride(
            learner_id=learner_id,
            brick_id=brick_id,
            collection_id=collection.id,
            native_text=brick.native_text,
            target_audio_path=brick.target_audio_path,
        )
        session.add(override)

    override.last_edit_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(override)
    collection_service.update_collection_difficulty(
        session, override.collection_id, learner_id
    )
    return override


def create_overrides_for_group(
    session: Session,
    learner_id: int,
    group_name: str,
    group_creator_id: int = 1,  # 1 is the hard coded default system creator
) -> int:
    # This function does not create collections for override bricks
    # because these are system bricks and user only have the permission to
    # change audio and native_text
    # That means, learner does not owns the system collection
    statement = (
        select(Collection)
        .where(
            Collection.creator_id == group_creator_id,
            Collection.group_name == group_name,
        )
        .options(selectinload(Collection.bricks))
    )
    collections = session.exec(statement).all()
    if not collections:
        return 0

    # Gather all unique bricks
    bricks = {
        brick.id: brick
        for collection in collections
        for brick in collection.bricks or []
    }
    if not bricks:
        return 0

    # Find existing overrides for learner_id
    existing_statement = select(BrickOverride.brick_id).where(
        BrickOverride.learner_id == learner_id,
        BrickOverride.brick_id.in_(bricks.keys()),
    )
    existing_overridden_brick_ids = set(session.exec(existing_statement).all())

    # Create missing overrides
    created_count = 0
    for brick_id in bricks.keys():
        if brick_id not in existing_overridden_brick_ids:
            override = BrickOverride(
                learner_id=learner_id,
                brick_id=brick_id,
                collection_id=bricks[brick_id].collection_id,
                native_text=bricks[brick_id].native_text,
                target_audio_path=bricks[brick_id].target_audio_path,
            )
            session.add(override)
            created_count += 1
    session.commit()
    return created_count
