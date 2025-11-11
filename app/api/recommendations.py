# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.services import readings as reading_service
from app.services import users as user_service
from app.services import recommendation_states as recommendation_state_service
from app.schemas import RecommendItemRequest, RecommendItemResponse
import numpy as np
from stable_baselines3 import PPO

router = APIRouter(prefix="/recommendation", tags=["Recommendations"])

MODEL_PATH = "./ai_models/ppo_user_sim_continuous.zip"
model = PPO.load(MODEL_PATH)


@router.post("/recommend", response_model=list[RecommendItemResponse])
def recommend_api(req: RecommendItemRequest, session: Session = Depends(get_session)):
    batch_size = 3

    user = user_service.get_user_by_username(session, req.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = user_service.refresh_and_get_user(session, user.id, interacted_only=True)
    obs = np.frombuffer(user.user_state_emb, dtype=np.float32).copy()

    action, _ = model.predict(obs, deterministic=False)
    recommended_nearest_readings = reading_service.get_nearest_readings(session, action, k=batch_size)

    # these are new user states we create in prior to the real interaction, 
    # so when the real interaction comes, we can just add the log and this will become true states
    new_recommendation_states = recommendation_state_service.create_recommendation_states(session, user, recommended_nearest_readings)

    recommendations = []
    for i in range(batch_size):
        recommendations.append(RecommendItemResponse(recommendation_state=new_recommendation_states[i], item=recommended_nearest_readings[i]))

    return recommendations


