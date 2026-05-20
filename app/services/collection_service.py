from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, or_, select

from app.database import Brick, BrickOverride, Collection, Review
from app.services import brick_override_service, brick_service
from schemas.cefr import CEFR_MAPPING


def is_reserved_collection_name(name: str) -> bool:
    cleaned_name = name.strip()
    reserved_names = {"All", *CEFR_MAPPING.values()}
    return cleaned_name in reserved_names


def get_pending_collections(
    session: Session,
    learner_id: int,
) -> list:
    """
    A pending collection is a collection contains his pending bricks.

    Note: A pending brick can have many pending collections
    because brick and brick override are not in the same collection.
    """
    statement = (
        select(
            Collection,
            func.count(func.distinct(Brick.id)).label("brick_count"),
            func.count(func.distinct(Review.brick_id)).label("learned_count"),
        )
        .select_from(Brick)
        .join(
            BrickOverride,
            (BrickOverride.brick_id == Brick.id)
            & (BrickOverride.learner_id == learner_id),
            isouter=True,
        )
        .join(
            Collection,
            Collection.id
            == func.coalesce(
                BrickOverride.collection_id,
                Brick.collection_id,
            ),
        )
        .join(
            Review,
            (Review.brick_id == Brick.id) & (Review.learner_id == learner_id),
            isouter=True,
        )
        .where(
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            )
        )
        .group_by(Collection.id)
    )

    results = session.exec(statement).all()

    return [
        {
            **collection.model_dump(),
            "brick_count": brick_count,
            "learned_count": learned_count,
        }
        for collection, brick_count, learned_count in results
    ]


def get_or_create_collection(
    session: Session, collection_name: str, creator_id: str
) -> Collection:
    statement = select(Collection).where(
        Collection.name == collection_name, Collection.creator_id == creator_id
    )
    collection = session.exec(statement).first()

    if not collection:
        collection = Collection(
            name=collection_name,
            creator_id=creator_id,
        )
        session.add(collection)
        session.commit()
        session.refresh(collection)

    return collection


def delete_empty_collection(session: Session, collection_id: int):
    """Deletes a collection only if no bricks and no overrides remain."""
    if not collection_id:
        return

    collection = session.get(Collection, collection_id)
    if not collection:
        return

    # No need to check bricks because of the RESTRICT ON DELETE constraint
    override_exists = (
        session.scalar(
            select(BrickOverride)
            .where(BrickOverride.collection_id == collection_id)
            .limit(1)
        )
        is not None
    )

    if override_exists:
        print(
            f"Collection {collection_id} kept because it still has overrides."
        )
        return

    try:
        session.delete(collection)
        session.commit()
        print(f"Collection {collection_id} deleted because it was empty.")
    except IntegrityError:
        # This error happens if the RESTRICT rule is triggered
        # Forget about that delete attempt and go
        # back to the state we were in before I tried that
        session.rollback()
        print(f"Collection {collection_id} kept because it still has bricks.")


def delete_collection(
    session: Session,
    learner_id: int,
    collection_id: int,
) -> int:
    collection = session.get(Collection, collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    if collection.creator_id != learner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed"
        )

    # delete the brick overrides
    deleted_override_count = brick_override_service.delete_overrides(
        session, learner_id, collection_id
    )

    # delete the remaining bricks the learner owns
    stmt = select(Brick).where(Brick.collection_id == collection_id)
    bricks = session.exec(stmt).all()
    deleted_owned_brick_count = 0
    for brick in bricks:
        brick_service.delete_brick(session, learner_id, brick.id)
        deleted_owned_brick_count += 1

    return deleted_override_count + deleted_owned_brick_count


def rename_collection(
    session: Session,
    learner_id: int,
    collection_id: int,
    new_name: str,
) -> Collection:
    collection = session.get(Collection, collection_id)

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    if collection.creator_id != learner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed",
        )

    cleaned_name = new_name.strip()

    if not cleaned_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Collection name cannot be empty",
        )

    reserved_names = set(CEFR_MAPPING.values())
    reserved_names.add("All")

    if cleaned_name in reserved_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This collection name is reserved by the system",
        )

    collection.name = cleaned_name

    session.add(collection)
    session.commit()
    session.refresh(collection)

    return collection
