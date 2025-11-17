from sqlmodel import Session, create_engine
from app.services.item_embeddings import get_embedding_by_reading_id, init_user_embedding
from app.services import users
import numpy as np

engine = create_engine("sqlite:///database.db")
with Session(engine) as session:

    # Get embedding for reading id 1
    vec = init_user_embedding(session)
    print(vec.shape)
    print(vec)
    vec_b = vec.tobytes()
    vec2 = np.frombuffer(vec_b, dtype=vec.dtype)
    print(vec2.shape)
    print(vec2)
    print(vec.dtype)
    print(type(vec_b))


