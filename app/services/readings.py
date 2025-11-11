from sqlmodel import Session, select
from app.models import Reading, ObjectiveQuestion
from app.schemas import ReadingCreate, ObjectiveQuestionCreate
import random
import numpy as np
from app.services.item_embeddings import get_all_item_embeddings

def create_reading(session: Session, reading_create: ReadingCreate) -> Reading:
    reading = Reading.model_validate(reading_create)
    session.add(reading)
    session.commit()
    session.refresh(reading)
    return reading

def add_objective_question(session: Session, question_create: ObjectiveQuestionCreate) -> ObjectiveQuestion:
    question = ObjectiveQuestion.model_validate(question_create)
    session.add(question)
    session.commit()
    session.refresh(question)
    return question

def get_all_readings(session: Session) -> list[Reading]:
    readings = session.exec(select(Reading)).all()
    return readings

def get_full_reading_by_id(session: Session, id: int):
    return session.exec(select(Reading).where(Reading.id == id)).one()

def get_readings_by_ids(session: Session, item_ids: list[int]) -> list[Reading]:
    if not item_ids:
        return []
    stmt = select(Reading).where(Reading.id.in_(item_ids))
    readings = session.exec(stmt).all()
    return readings

def get_random_reading(session: Session) -> Reading | None:
    reading_ids = session.exec(select(Reading.id)).all()
    if not reading_ids:
        return None
    random_id = random.choice(reading_ids)
    return session.get(Reading, random_id)

def get_random_unseen_reading(session: Session, excluded_ids: list[int]) -> Reading:
    """
    Get a random reading that is NOT in excluded_ids.
    If all readings are already interacted, return any reading and log a warning.
    """
    stmt = select(Reading)
    if excluded_ids:
        stmt = stmt.where(Reading.id.not_in(excluded_ids))

    available_readings = session.exec(stmt).all()
    if not available_readings:
        # fallback: all readings are interacted, pick any reading
        all_readings = session.exec(select(Reading)).all()
        if not all_readings:
            raise ValueError("No readings found in the database")
        print("User has interacted with all readings. Returning a random reading anyway.")
        return random.choice(all_readings)

    return random.choice(available_readings)

def get_nearest_readings(session: Session, model_action_emb: np.ndarray, k: int = 3) -> list["Reading"]:
    # 1. Get embeddings and normalize
    item_embeddings, item_ids = get_all_item_embeddings(session)  # shape (num_items, dim), return IDs too
    item_embeddings_normed = item_embeddings / (np.linalg.norm(item_embeddings, axis=1, keepdims=True) + 1e-12)
    
    # 2. Normalize action embedding
    action_normed = model_action_emb / (np.linalg.norm(model_action_emb) + 1e-12)
    
    # 3. Compute cosine similarities
    sims = item_embeddings_normed @ action_normed  # shape: (num_items,)
    
    # 4. Get top-k indices
    nearest_indices = np.argsort(sims)[-k:][::-1]
    nearest_ids = [item_ids[i] for i in nearest_indices]
    
    # 5. Fetch corresponding readings from DB
    stmt = select(Reading).where(Reading.id.in_(nearest_ids))
    readings = session.exec(stmt).all()
    
    # Optional: sort readings by similarity
    id_to_sim = dict(zip(item_ids, sims))
    readings.sort(key=lambda r: id_to_sim[r.id], reverse=True)
    
    return readings