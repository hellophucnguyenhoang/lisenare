from datetime import datetime, timezone

from fastapi import status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, delete, select

from app.database import Brick, BrickOverride, Collection, LearningCard, Review
from app.exceptions import ErrorCode, RequestException
from app.services import collection_service


def save_override_for_brick(
    session: Session,
    learner_id: int,
    brick_id: int,
    collection_name: int,
) -> BrickOverride:
    """
    Create an override of a brick in a provided collection name for learner.
    It creates a new collection or added to an existing one.
    """

    # validate reserved name
    if collection_service.is_reserved_collection_name(collection_name):
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(f"Reserved collection name: {collection_name}"),
            error_code=ErrorCode.RESERVED_COLLECTION_NAME,
        )

    # get brick
    brick = session.get(Brick, brick_id)
    if not brick:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{brick_id=} not found",
        )

    # find or create collection
    stmt = select(Collection).where(
        Collection.creator_id == learner_id,
        Collection.name == collection_name,
    )

    collection = session.exec(stmt).first()

    if not collection:
        collection = Collection(
            name=collection_name,
            creator_id=learner_id,
        )

        session.add(collection)
        session.flush()

    # find or create override
    stmt = select(BrickOverride).where(
        BrickOverride.learner_id == learner_id,
        BrickOverride.brick_id == brick_id,
    )

    override = session.exec(stmt).first()

    if not override:
        override = BrickOverride(
            learner_id=learner_id,
            brick_id=brick_id,
            native_text=brick.native_text,
            target_audio_path=brick.target_audio_path,
        )

        session.add(override)
    else:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(
                "Brick override already exists for "
                f"learner_id={override.learner_id}, "
                f"brick_id={override.brick_id}"
            ),
            error_code=ErrorCode.BRICK_OVERRIDE_ALREADY_EXISTS,
        )

    # attach override to collection and update timestamp
    override.collection_id = collection.id
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
        raise RequestException(
            status_code=status.HTTP_409_CONFLICT,
            debug_message=f"Learner {learner_id=} already \
                have collection {collection.name}.",
            error_code=ErrorCode.COLLECTION_ALREADY_EXISTS,
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
    # Due to the ondelete="CASCADE" constraint on BrickOverride.collection_id,
    # this step automatically handles clearing out the matching BrickOverride rows
    session.delete(collection)

    session.commit()
    return deleted_count
