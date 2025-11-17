from sqlmodel import Session, create_engine
from app.services import readings
import numpy as np
from reading_env import Reader

def reading_vector(reading):
    return np.frombuffer(reading.reading_embedding.vector_blob, dtype=np.float32).copy()

engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    user_reading = readings.get_full_reading_by_id(session, 404)
    print(f"Init user level: {user_reading.difficulty}")

    user_preference = reading_vector(user_reading)
    noise = np.random.normal(loc=0, scale=0.2, size=user_preference.shape)
    user_preference += noise
    recent_embs = []
    recent_ids = []
    recent_levels = []
    for i in range(10):
        nearest_readings = readings.get_nearest_readings(session, user_preference)
        nearest_levels = [(reading.id, reading.difficulty) for reading in nearest_readings]

        recommeded_reading = nearest_readings[0]
        recommend_reading_vector = reading_vector(recommeded_reading)
        diversity = Reader.diversity(np.array(recent_embs))
        print(nearest_levels, recent_ids, recent_levels, diversity)

        user_preference = Reader.update_user_preference(user_preference, recommend_reading_vector, -1, update_alpha=0.5)
        recent_embs.append(recommend_reading_vector)
        recent_ids.append(recommeded_reading.id)
        recent_levels.append(recommeded_reading.difficulty)
        if len(recent_embs) > 5:
            recent_embs.pop(0)
            recent_ids.pop(0)
            recent_levels.pop(0)
    
