from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.database import Brick, BrickOverride, Collection


def save_override_for_brick(
    session: Session,
    learner_id: int,
    brick_id: int,
    native_text: str | None = None,
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
        override = BrickOverride(
            learner_id=learner_id,
            brick_id=brick_id,
        )
        session.add(override)

    if native_text is not None:
        override.native_text = native_text
    override.last_edit_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(override)
    return override


def create_overrides_for_group(
    session: Session,
    learner_id: int,
    group_name: str,
    group_creator_id: int = 1,  # 1 is the hard coded default system creator
) -> int:
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
                native_text=bricks[brick_id].native_text,
                target_audio_uri=bricks[brick_id].target_audio_uri,
            )
            session.add(override)
            created_count += 1
    session.commit()
    return created_count
