from app.database import Collection, CollectionBrick
from sqlmodel import Session, select
from sqlalchemy import func

def get_user_collections(session: Session, learner_id: int) -> list[dict]:
    statement = (
        select(Collection, func.count(CollectionBrick.brick_id).label("brick_count"))
        .outerjoin(CollectionBrick, Collection.id == CollectionBrick.collection_id)
        .where(Collection.creator_id == learner_id)
        .group_by(Collection.id)
    )
    
    results = session.exec(statement).all()
    
    # results will be a list of tuples: [(Collection, count), (Collection, count), ...]
    # We combine them into a list of dictionaries or objects for the schema
    collections_with_count = []
    for collection, brick_count in results:
        # Create a dictionary compatible with CollectionRead
        data = collection.model_dump()
        data["brick_count"] = brick_count
        collections_with_count.append(data)
        
    return collections_with_count

def create_collection(session: Session, learner_id: int, collection_name: str) -> Collection:
    collection = Collection(name=collection_name, creator_id=learner_id)
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection
