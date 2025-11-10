from sqlmodel import Session, create_engine
from app.services.item_embeddings import create_item_embeddings, get_item_embedding_by_reading_id


engine = create_engine("sqlite:///database.db")

with Session(engine) as session:
    # Create (or update) embeddings for all readings
    create_item_embeddings(session, include_questions=False)

    # Get embedding for reading id 1
    vec = get_item_embedding_by_reading_id(session, 1)
    if vec is not None:
        print("Embedding shape:", vec.shape)
    else:
        print("No embedding for reading 1")
