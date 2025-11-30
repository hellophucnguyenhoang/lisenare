from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.services import readings as reading_service
from app.services import users as user_service
from app.services import study_sessions as study_session_services
import numpy as np
from stable_baselines3 import PPO
import reading_env
from app.config import settings
from app.schemas import RecommendedItem, ReadingRead

router = APIRouter(prefix="/recommendation", tags=["Recommendations"])

MODEL_PATH = "./ai_models/ppo_reading_rec_2_1024.zip"
model = PPO.load(MODEL_PATH)

@router.post("/recommend", response_model=list[RecommendedItem])
def recommend_api(username: str, batch_size: int = settings.recommend_batch_size, session: Session = Depends(get_session)):
    user = user_service.get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    preferred_topic_ids = [t.id for t in user.preference_topics]
    if not preferred_topic_ids:
        preferred_topic_ids = []

    recent_item_ids, recent_embs, recent_rewards = study_session_services.get_recent_history(session, user_id=user.id)
    state = reading_env.ReadingRecEnvContinuous.get_obs(
        emb_dim=settings.item_embedding_dim,
        recent_embs=recent_embs,
        recent_rewards=recent_rewards
    )
    action, _ = model.predict(state, deterministic=False)
    recommended_readings = reading_service.get_relatest_readings(
        session, 
        action, 
        preferred_topic_ids, 
        recent_item_ids, 
        recent_embs, 
        batch_size=batch_size)
    item_ids = [reading.id for reading in recommended_readings]
    study_sessions = study_session_services.create_batch(session, user.id, item_ids)

    recommended_items = []
    for study_session, reading in zip(study_sessions, recommended_readings):
        item = ReadingRead.model_validate(reading)
        item.topic_name = reading.topic.name
        recommended_items.append(
            RecommendedItem(
                study_session_id=study_session.id,
                batch_id=study_session.batch_id,
                item=item
            )
        )
    return recommended_items


