from app.database import Collection, CollectionBrick
from sqlmodel import Session, select, func
from app.schemas import CollectionCreate

def get_user_collections(session: Session, learner_id: int, group_name: str, limit: int, offset: int) -> list[dict]:
    statement = (
        select(Collection, func.count(CollectionBrick.brick_id).label("brick_count"))
        .outerjoin(CollectionBrick, Collection.id == CollectionBrick.collection_id)
        .where(Collection.creator_id == learner_id, Collection.group_name == group_name)
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
    statement = (
        select(func.count(Collection.id))
        .where(
            Collection.creator_id == learner_id,
            Collection.group_name == group_name
        )
    )
    return session.exec(statement).one()

def create_collection(session: Session, learner_id: int, collection_create: CollectionCreate) -> Collection:
    collection = Collection(
        name=collection_create.name, 
        group_name=collection_create.group_name,
        creator_id=learner_id
    )
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection
