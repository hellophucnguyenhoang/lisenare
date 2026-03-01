from sqlmodel import Session, select, func, or_

from app.database import Collection, CollectionBrick, BrickOverride, Brick
from app.schemas import CollectionCreate, CollectionRead


def get_learning_bricks_subquery(learner_id: int):
    return (
        select(Brick.id)
        .outerjoin(
            BrickOverride,
            (BrickOverride.brick_id == Brick.id)
            & (BrickOverride.learner_id == learner_id),
        )
        .where(
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            )
        )
        .subquery()
    )


def get_user_learning_collections(
    session: Session,
    learner_id: int,
    group_name: str,
    limit: int,
    offset: int,
) -> list[CollectionRead]:
    # Subquery: bricks learner is learning
    learning_bricks_subq = get_learning_bricks_subquery(learner_id)

    # Main query
    statement = (
        select(
            Collection,
            func.count(CollectionBrick.brick_id).label("brick_count"),
        )
        .join(
            CollectionBrick,
            Collection.id == CollectionBrick.collection_id,
        )
        .join(
            learning_bricks_subq,
            CollectionBrick.brick_id == learning_bricks_subq.c.id,
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
    for collection, brick_count in results:
        data = collection.model_dump()
        data["brick_count"] = brick_count
        collections_with_count.append(data)
    return collections_with_count


def get_user_collections(
    session: Session, learner_id: int, group_name: str, limit: int, offset: int
) -> list[CollectionRead]:
    statement = (
        select(
            Collection,
            func.count(CollectionBrick.brick_id).label("brick_count"),
        )
        .outerjoin(
            CollectionBrick, Collection.id == CollectionBrick.collection_id
        )
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


def count_user_collections(
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
    learning_bricks_subq = get_learning_bricks_subquery(learner_id)
    statement = (
        select(
            Collection.group_name,
            func.count(func.distinct(Collection.id)).label("collection_count"),
        )
        .join(CollectionBrick, Collection.id == CollectionBrick.collection_id)
        .join(
            learning_bricks_subq,
            CollectionBrick.brick_id == learning_bricks_subq.c.id,
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
