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

MODEL_PATH = "./ai_models/ppo_user_sim_continuous.zip"
model = PPO.load(MODEL_PATH)


@router.post("/recommend", response_model=list[RecommendedItem])
def recommend_api(username: str, batch_size: int = settings.recommend_batch_size, session: Session = Depends(get_session)):
    user = user_service.get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user, recent_embs, recent_rewards, recent_sim01s = study_session_services.update_user_preference(session, user_id=user.id)
    user_preference_emb = np.frombuffer(user.preference_emb, dtype=np.float32)
    state = reading_env.ReadingRecEnvContinuous.get_obs(
        user_preference=user_preference_emb,
        recent_embs=recent_embs,
        recent_rewards=recent_rewards,
        recent_sim01s=recent_sim01s
    )
    action, _ = model.predict(state, deterministic=False)
    recommended_readings = reading_service.get_nearest_readings(session, action, k=batch_size)
    item_ids = [reading.id for reading in recommended_readings]
    study_sessions = study_session_services.create_batch(session, user.id, item_ids)

    recommended_items = []
    for study_session, reading in zip(study_sessions, recommended_readings):
        recommended_items.append(
            RecommendedItem(
                study_session_id=study_session.id,
                batch_id=study_session.batch_id,
                item=ReadingRead.model_validate(reading)
            )
        )

    return recommended_items
