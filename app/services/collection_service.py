from fastapi import status
from sqlmodel import Session, func, select

from app.database import Brick, BrickReview, Collection
from app.exceptions import RequestException

from .tag_service import fetch_tags_for_entities


def get_or_create_collection(
    session: Session, collection_name: str, creator_id: int
) -> Collection:
    stmt = select(Collection).where(
        Collection.name == collection_name, Collection.creator_id == creator_id
    )
    collection = session.exec(stmt).first()

    if not collection:
        collection = Collection(
            name=collection_name,
            creator_id=creator_id,
        )
        session.add(collection)
        session.commit()
        session.refresh(collection)

    return collection


def get_collections(
    session: Session, creator_id: int
) -> list[tuple[Collection, int, int, list]]:
    # Get all collections for this creator
    collections = session.exec(
        select(Collection).where(Collection.creator_id == creator_id)
    ).all()

    if not collections:
        return []

    collection_ids = [c.id for c in collections]

    # Get total brick counts per collection
    brick_counts = dict(
        session.exec(
            select(Brick.collection_id, func.count(Brick.id))
            .where(Brick.collection_id.in_(collection_ids))
            .group_by(Brick.collection_id)
        ).all()
    )

    # Get learned brick counts per collection
    learned_counts = dict(
        session.exec(
            select(Brick.collection_id, func.count(Brick.id))
            .join(BrickReview, BrickReview.brick_id == Brick.id)
            .where(
                Brick.collection_id.in_(collection_ids),
                BrickReview.learner_id == creator_id,
            )
            .group_by(Brick.collection_id)
        ).all()
    )

    collection_tags = fetch_tags_for_entities(
        session, collection_ids, "Collection"
    )

    # Merge everything into a clear, flat tuple list
    return [
        (
            col,
            brick_counts.get(col.id, 0),
            learned_counts.get(col.id, 0),
            collection_tags[col.id],
        )
        for col in collections
    ]


def delete_collection(
    session: Session,
    creator_id: int,
    collection_id: int,
) -> str:
    collection = session.get(Collection, collection_id)
    if not collection:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{collection_id=} not found",
        )

    if collection.creator_id != creator_id:
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} is not the creator to delete {collection_id=}",
        )

    session.delete(collection)
    session.commit()

    return "COLLECTION_DELETED"


def rename_collection(
    session: Session,
    creator_id: int,
    collection_id: int,
    new_name: str,
) -> Collection:
    cleaned_name = new_name.strip()
    if not cleaned_name:
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message="New collection name is empty",
        )

    collection = session.get(Collection, collection_id)
    if not collection:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"{collection_id=} not found",
        )

    if collection.creator_id != creator_id:
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message=f"{creator_id=} not the creator to edit {collection_id=}",
        )

    existing_stmt = select(Collection).where(
        Collection.creator_id == creator_id,
        Collection.name == cleaned_name,
        Collection.id != collection_id,
    )
    if session.exec(existing_stmt).first():
        raise RequestException(
            status_code=status.HTTP_409_CONFLICT,
            debug_message=f"Collection named '{cleaned_name}' already exists for this learner",
        )

    collection.name = cleaned_name
    session.add(collection)
    session.commit()
    session.refresh(collection)

    return collection
