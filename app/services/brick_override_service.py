from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, delete, select

from app.database import Brick, BrickOverride, Collection, LearningCard, Review
from utils import text_utils


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

    return override


def create_overrides(
    session: Session,
    learner_id: int,
    collection_id: int,
) -> tuple[int, int | None]:
    # A learner only have the permission to change audio and native_text
    statement = (
        select(Collection)
        .where(Collection.id == collection_id)
        .options(selectinload(Collection.bricks))
    )
    collection = session.exec(statement).first()
    if not collection:
        return 0, None

    # Gather all bricks need to override
    bricks_map = {brick.id: brick for brick in collection.bricks or []}
    if not bricks_map:
        return 0, None

    # Find or create the learner's personal collection clone
    user_col_statement = select(Collection).where(
        Collection.creator_id == learner_id, Collection.name == collection.name
    )
    user_collection = session.exec(user_col_statement).first()

    if user_collection:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Collection name already exits but no new collection name provided.",
        )

    user_collection = Collection(
        name=collection.name,
        creator_id=learner_id,
    )
    session.add(user_collection)
    session.flush()

    # Find existing overrides for learner_id to skip
    # Do not override the bricks users already override
    existing_statement = select(BrickOverride.brick_id).where(
        BrickOverride.learner_id == learner_id,
        BrickOverride.brick_id.in_(bricks_map.keys()),
    )
    existing_overridden_brick_ids = set(session.exec(existing_statement).all())

    # Create missing overrides
    created_count = 0
    for brick_id, system_brick in bricks_map.items():
        if brick_id not in existing_overridden_brick_ids:
            override = BrickOverride(
                learner_id=learner_id,
                brick_id=brick_id,
                collection_id=user_collection.id,
                native_text=system_brick.native_text,
                target_audio_path=system_brick.target_audio_path,
            )
            session.add(override)
            created_count += 1
    session.commit()
    return created_count, user_collection.id


def delete_overrides(
    session: Session,
    learner_id: int,
    collection_id: int,
) -> int:
    """
    Safely removes a learner's personalized cloned collection.
    Clears out the associated reviews and learning cards for those specific bricks,
    and drops the collection container (which cascades into the overrides).
    """
    # Verify the collection exists and actually belongs to the learner
    collection = session.get(Collection, collection_id)
    if not collection or collection.creator_id != learner_id:
        return 0

    # Extract the exact brick IDs that the user has overridden inside this collection
    statement = select(BrickOverride.brick_id).where(
        and_(
            BrickOverride.collection_id == collection_id,
            BrickOverride.learner_id == learner_id,
        )
    )
    overridden_brick_ids = session.exec(statement).all()

    deleted_count = len(overridden_brick_ids)
    if deleted_count == 0:
        return 0

    # Explicitly delete the user's localized study progress for these exact bricks.
    # We do this first because Review/LearningCard do not cascade from BrickOverride.
    session.exec(
        delete(LearningCard).where(
            and_(
                LearningCard.learner_id == learner_id,
                LearningCard.brick_id.in_(overridden_brick_ids),
            )
        )
    )

    session.exec(
        delete(Review).where(
            and_(
                Review.learner_id == learner_id,
                Review.brick_id.in_(overridden_brick_ids),
            )
        )
    )

    # Delete the cloned Collection container.
    # Due to your ondelete="CASCADE" constraint on BrickOverride.collection_id,
    # this step automatically handles clearing out the matching BrickOverride rows
    session.delete(collection)

    session.commit()
    return deleted_count
