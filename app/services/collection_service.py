from sqlmodel import Session, select, func, or_

from app.database import (
    Collection,
    CollectionBrick,
    BrickOverride,
    Brick,
    Review,
)
from app.schemas import CollectionCreate, CollectionRead


def temp_get_data(session: Session, learner_id=2, group_name="A1"):
    pending_bricks = get_pending_bricks_subquery(learner_id)

    pending_collection_bricks = (
        select(CollectionBrick)
        .join(
            pending_bricks,
            CollectionBrick.brick_id == pending_bricks.columns.id,
        )
        .subquery()
    )

    pending_collections = (
        select(
            Collection.id,
            func.count(pending_collection_bricks.columns.brick_id).label(
                "brick_count"
            ),
        )
        .join(
            pending_collection_bricks,
            Collection.id == pending_collection_bricks.columns.collection_id,
        )
        .where(Collection.group_name == group_name)
        .group_by(Collection.id)
    )

    result = session.exec(pending_collections).all()
    return result


def get_pending_bricks_subquery(learner_id: int):
    return (
        select(Brick.id)
        .distinct()
        .join(BrickOverride, isouter=True)
        .where(
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            )
        )
        .subquery()
    )


def get_learner_pending_collections(
    session: Session,
    learner_id: int,
    group_name: str,
    limit: int,
    offset: int,
) -> list[CollectionRead]:

    pending_bricks_subq = get_pending_bricks_subquery(learner_id)

    statement = (
        select(
            Collection,
            func.count(CollectionBrick.brick_id).label("brick_count"),
            func.count(func.distinct(Review.brick_id)).label("learned_count"),
        )
        .join(CollectionBrick)
        .join(
            pending_bricks_subq,
            CollectionBrick.brick_id == pending_bricks_subq.c.id,
        )
        .outerjoin(
            Review,
            (Review.brick_id == CollectionBrick.brick_id)
            & (Review.learner_id == learner_id),
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


def get_learner_collections(
    session: Session, learner_id: int, group_name: str, limit: int, offset: int
) -> list[CollectionRead]:
    statement = (
        select(
            Collection,
            func.count(CollectionBrick.brick_id).label("brick_count"),
        )
        .outerjoin(CollectionBrick)
        .where(
            Collection.creator_id == learner_id,
            Collection.group_name == group_name,
        )
        .group_by(Collection.id)
        .order_by(Collection.difficulty_score, Collection.name, Collection.id)
        .limit(limit)
        .offset(offset)
    )
    results = session.exec(statement).all()
    collections_with_count = []
    for collection, brick_count in results:
        data = collection.model_dump()
        data["brick_count"] = brick_count
        collections_with_count.append(data)
    return collections_with_count


def count_learner_collections(
    session: Session,
    learner_id: int,
    group_name: str,
) -> int:
    statement = select(func.count(Collection.id)).where(
        Collection.creator_id == learner_id,
        Collection.group_name == group_name,
    )
    return session.exec(statement).one()


def create_collection(
    session: Session, learner_id: int, collection_create: CollectionCreate
) -> Collection:
    collection = Collection(
        name=collection_create.name,
        group_name=collection_create.group_name,
        creator_id=learner_id,
    )
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection


def get_learning_collection_group_stats(
    session: Session,
    learner_id: int,
) -> list[dict]:
    pending_bricks_subq = get_pending_bricks_subquery(learner_id)
    statement = (
        select(
            Collection.group_name,
            func.count(func.distinct(Collection.id)).label("collection_count"),
        )
        .join(CollectionBrick, Collection.id == CollectionBrick.collection_id)
        .join(
            pending_bricks_subq,
            CollectionBrick.brick_id == pending_bricks_subq.c.id,
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


def get_collection_group_stats(
    session: Session, learner_id: int
) -> list[dict]:
    statement = (
        select(
            Collection.group_name,
            func.count(Collection.id).label("collection_count"),
        )
        .where(Collection.creator_id == learner_id)
        .group_by(Collection.group_name)
    )
    results = session.exec(statement).all()
    return [
        {"group_name": group_name, "collection_count": collection_count}
        for group_name, collection_count in results
    ]
