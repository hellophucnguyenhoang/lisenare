from sqlmodel import Session, select, func, or_

from app.database import (
    Collection,
    BrickOverride,
    Brick,
    Review,
)
from app.schemas import CollectionRead
from . import text_service


def get_collections(
    session: Session,
    learner_id: int,
) -> list[CollectionRead]:
    statement = select(Collection).where(Collection.creator_id == learner_id)
    collections = session.exec(statement).all()
    return collections


def get_pending_bricks(session: Session, learner_id: int, collection_id: int):
    """
    A brick is considered pending of a learner if it's created or has a
    override version created by that learner.
    """
    statement = (
        select(Brick)
        .join(BrickOverride, isouter=True)
        .where(
            Brick.collection_id == collection_id,
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            ),
        )
    )
    return session.exec(statement).all()


def get_pending_bricks_subquery(learner_id: int):
    """
    A brick is considered pending of a learner if it's created or has a
    override version created by that learner.
    """
    return (
        select(Brick)
        .join(BrickOverride, isouter=True)
        .where(
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            )
        )
        .subquery()
    )


def get_pending_collections(
    session: Session,
    learner_id: int,
    group_name: str,
    limit: int,
    offset: int,
) -> list[CollectionRead]:
    # Get all the pending bricks
    # Join with the Review to know the current learning state of them
    # Aggregate their collection information

    pending_bricks_subq = get_pending_bricks_subquery(learner_id)

    statement = (
        select(
            Collection,
            func.count(pending_bricks_subq.c.id).label("brick_count"),
            func.count(func.distinct(Review.brick_id)).label("learned_count"),
        )
        .select_from(Collection)
        .join(
            pending_bricks_subq,
            Collection.id == pending_bricks_subq.c.collection_id,
        )
        .join(
            Review,
            (Review.learner_id == learner_id)
            & (Review.brick_id == pending_bricks_subq.c.id),
            isouter=True,
        )
        .where(Collection.group_name == group_name)
        .group_by(Collection.id)
        .order_by(
            Collection.difficulty_score,
            Collection.name,
            Collection.id,
        )
        .limit(limit)
        .offset(offset)
    )

    results = session.exec(statement).all()

    collections_with_count = []

    for collection, brick_count, learned_count in results:
        data = collection.model_dump()
        data["brick_count"] = brick_count
        data["learned_count"] = learned_count
        collections_with_count.append(data)

    return collections_with_count


def get_or_create_collection(
    session: Session, collection_name: str, group_name: str, creator_id: str
) -> Collection:
    statement = select(Collection).where(
        Collection.name == collection_name, Collection.creator_id == creator_id
    )
    collection = session.exec(statement).first()

    if not collection:
        collection = Collection(
            name=collection_name,
            group_name=group_name,
            creator_id=creator_id,
            difficulty_score=0.0,
        )
        session.add(collection)
        session.commit()
        session.refresh(collection)

    return collection


def update_collection_difficulty(session: Session, collection_id: int):
    statement = select(Brick).where(Brick.collection_id == collection_id)
    bricks = session.exec(statement).all()

    if bricks:
        sum_score = sum(
            text_service.log_frequency(b.target_text) for b in bricks
        )
        collection = session.get(Collection, collection_id)
        if collection:
            collection.difficulty_score = sum_score
            session.add(collection)
            session.commit()


def get_pending_collection_group_stats(
    session: Session,
    learner_id: int,
) -> list[dict]:
    pending_bricks_subq = get_pending_bricks_subquery(learner_id)
    statement = (
        select(
            Collection.group_name,
            func.count(func.distinct(Collection.id)).label("collection_count"),
        )
        .join(
            pending_bricks_subq,
            Collection.id == pending_bricks_subq.c.collection_id,
        )
        .group_by(Collection.group_name)
    )
    results = session.exec(statement).all()
    return [
        {
            "group_name": group_name,
            "collection_count": collection_count,
        }
        for group_name, collection_count in results
    ]
