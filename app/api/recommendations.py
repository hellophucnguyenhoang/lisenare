# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.services import readings as reading_service
from app.services import users as user_service
from app.services import user_states as user_state_service
from app.schemas import RecommendItemRequest, RecommendItemResponse, UserStateRead
import numpy as np
from stable_baselines3 import PPO

router = APIRouter(prefix="/recommendation", tags=["Recommendations"])

MODEL_PATH = "./ai_models/ppo_user_sim.zip"
model = PPO.load(MODEL_PATH)

@router.post("/recommend", response_model=list[RecommendItemResponse])
def recommend_api(req: RecommendItemRequest, session: Session = Depends(get_session)):

    batch_size = 3
    recommendations = []

    for i in range(batch_size):

        obs = user_service.get_current_state(session, req.username, include_future=True)
        action, _ = model.predict(obs, deterministic=True)
        item_id = int(action)
        print(f'Recommended item ID{i}:', item_id)

        # update user history
        user_state = user_state_service.create_user_state(session, req.username, item_id)
        recommended_reading = reading_service.get_full_reading_by_id(session, item_id)

        recommendations.append(RecommendItemResponse(user_state=user_state, item=recommended_reading))

    return recommendations

