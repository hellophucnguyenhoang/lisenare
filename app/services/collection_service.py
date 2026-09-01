from fastapi import status
from sqlmodel import Session, func, select

from app.database import Brick, BrickReview, Collection
from app.exceptions import ErrorCode, RequestException
from app.schemas import CollectionCreate, CollectionUpdate

from .tag_service import (
    delete_tags_for_entity,
    fetch_tags_for_entities,
    fetch_tags_for_entity,
    set_tags_for_entity,
)


def create_collection(
    session: Session,
    creator_id: int,
    collection_create: CollectionCreate,
) -> tuple[Collection, list[str]]:
    cleaned_name = collection_create.name.strip()
    if not cleaned_name:
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message="Collection name cannot be empty",
        )

    existing_stmt = select(Collection).where(
        Collection.creator_id == creator_id,
        Collection.name == cleaned_name,
    )
    if session.exec(existing_stmt).first():
        raise RequestException(
            status_code=status.HTTP_409_CONFLICT,
            debug_message=f"Collection named '{cleaned_name}' already exists for this learner",
            error_code=ErrorCode.COLLECTION_ALREADY_EXISTS,
        )

    collection = Collection(
        name=cleaned_name,
        description=collection_create.description,
        creator_id=creator_id,
    )
    session.add(collection)
    session.flush()

    tags: list[str] = []
    if collection_create.tags:
        tags = set_tags_for_entity(
            session=session,
            entity_id=collection.id,
            entity_type="Collection",
            tag_names=collection_create.tags,
            creator_id=creator_id,
        )

    session.commit()
    session.refresh(collection)

    return collection, tags


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

    delete_tags_for_entity(session, collection_id, "Collection")
    session.delete(collection)
    session.commit()

    return "COLLECTION_DELETED"


def update_collection(
    session: Session,
    creator_id: int,
    collection_id: int,
    collection_update: CollectionUpdate,
) -> tuple[Collection, int, int, list[str]]:
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

    if collection_update.name is not None:
        cleaned_name = collection_update.name.strip()
        if not cleaned_name:
            raise RequestException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                debug_message="New collection name is empty",
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
                error_code=ErrorCode.COLLECTION_ALREADY_EXISTS,
            )
        collection.name = cleaned_name

    if collection_update.description is not None:
        collection.description = collection_update.description

    session.add(collection)

    if collection_update.tags is not None:
        tags = set_tags_for_entity(
            session=session,
            entity_id=collection.id,
            entity_type="Collection",
            tag_names=collection_update.tags,
            creator_id=creator_id,
        )
    else:
        tags = fetch_tags_for_entity(session, collection.id, "Collection")

    session.commit()
    session.refresh(collection)

    brick_count = (
        session.exec(
            select(func.count(Brick.id)).where(
                Brick.collection_id == collection.id
            )
        ).one()
        or 0
    )

    learned_count = (
        session.exec(
            select(func.count(Brick.id))
            .join(BrickReview, BrickReview.brick_id == Brick.id)
            .where(
                Brick.collection_id == collection.id,
                BrickReview.learner_id == creator_id,
            )
        ).one()
        or 0
    )

    return collection, brick_count, learned_count, tags


def rename_collection(
    session: Session,
    creator_id: int,
    collection_id: int,
    new_name: str,
) -> Collection:
    col, _, _, _ = update_collection(
        session=session,
        creator_id=creator_id,
        collection_id=collection_id,
        collection_update=CollectionUpdate(name=new_name),
    )
    return col
