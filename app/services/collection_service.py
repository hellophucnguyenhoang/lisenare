from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, asc, desc, func, select

from app.database import Brick, Collection, Review
from app.schemas import CollectionRead, CollectionSort, CollectionStatus

from . import brick_service, text_service


def get_collections(
    session: Session,
    learner_id: int,
) -> list[CollectionRead]:
    statement = select(Collection).where(Collection.creator_id == learner_id)
    collections = session.exec(statement).all()
    return collections


def get_pending_collections(
    session: Session,
    learner_id: int,
    group_name: str | None = None,
    status: CollectionStatus = CollectionStatus.ALL,
    sort_by: CollectionSort = CollectionSort.recommended,
    limit: int | None = None,
    offset: int | None = None,
) -> list[CollectionRead]:
    # Get all the pending bricks
    # Join with the Review to know the current learning state of them
    # Aggregate their collection information
    # Apply pagination and sorting

    pending_bricks_subq = brick_service.get_pending_bricks_subquery(learner_id)

    statement = (
        select(
            Collection,
            func.count(func.distinct(pending_bricks_subq.c.id)).label(
                "brick_count"
            ),
            func.count(func.distinct(Review.brick_id)).label("learned_count"),
            func.max(pending_bricks_subq.c.last_edit_at).label(
                "latest_brick_edit"
            ),
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
    )

    if group_name:
        statement = statement.where(Collection.group_name == group_name)

    statement = statement.group_by(Collection.id)

    total_bricks_count = func.count(func.distinct(pending_bricks_subq.c.id))
    learned_bricks_count = func.count(func.distinct(Review.brick_id))

    if status == CollectionStatus.NOT_STARTED:
        # Chưa học brick nào
        statement = statement.having(learned_bricks_count == 0)

    elif status == CollectionStatus.IN_PROGRESS:
        # Đã học ít nhất 1 brick VÀ chưa học hết
        statement = statement.having(
            (learned_bricks_count > 0)
            & (learned_bricks_count < total_bricks_count)
        )

    elif status == CollectionStatus.COMPLETED:
        # Số lượng brick đã học bằng tổng số brick
        statement = statement.having(
            (learned_bricks_count == total_bricks_count)
            & (total_bricks_count > 0)  # Đảm bảo collection không trống
        )

    # --- Sorting Logic ---
    if sort_by == CollectionSort.newest:
        statement = statement.order_by(
            desc("latest_brick_edit"), Collection.id
        )
    elif sort_by == CollectionSort.az:
        # Sort by name A -> Z
        statement = statement.order_by(asc(Collection.name), Collection.id)
    elif sort_by == CollectionSort.za:
        # Sort by name Z -> A
        statement = statement.order_by(desc(Collection.name), Collection.id)
    else:
        # Default "recommended" sorting
        statement = statement.order_by(
            Collection.difficulty_score,
            Collection.name,
            Collection.id,
        )

    if limit is not None:
        statement = statement.limit(limit)

    if offset is not None:
        statement = statement.offset(offset)

    results = session.exec(statement).all()

    collections_with_count = []
    for collection, brick_count, learned_count, _ in results:
        data = collection.model_dump()
        data["brick_count"] = brick_count
        data["learned_count"] = learned_count
        collections_with_count.append(data)

    return collections_with_count


def get_pending_groups(
    session: Session,
    learner_id: int,
) -> list[str]:
    collections_with_count = get_pending_collections(session, learner_id)
    group_names = set([coll["group_name"] for coll in collections_with_count])
    return list(group_names)


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


def get_pending_collection_group_stats(
    session: Session,
    learner_id: int,
) -> list[dict]:
    pending_bricks_subq = brick_service.get_pending_bricks_subquery(learner_id)
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


def delete_empty_collection(session: Session, collection_id: int):
    """Deletes a collection only if no bricks and no overrides remain."""
    if not collection_id:
        return

    collection = session.get(Collection, collection_id)
    if not collection:
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
        print(
            f"Collection {collection_id} kept because it still has bricks or overrides."
        )
