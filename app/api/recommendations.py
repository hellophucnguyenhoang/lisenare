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

    # IDs the user has already interacted with
    user_interacted_items = user_service.get_interacted_items(session, req.username, include_future=True)

    for i in range(batch_size):
        # pick a random reading (will always return a reading, logs a warning if all are read)
        random_reading = reading_service.get_random_unseen_reading(session, user_interacted_items)
        item_id = random_reading.id
        print(f'Recommended item ID {i}:', item_id)

        # update user state
        user_state = user_state_service.create_user_state(session, req.username, item_id)

        # append to response
        recommendations.append(RecommendItemResponse(user_state=user_state, item=random_reading))

        # add to interacted list to avoid duplicates in this batch
        user_interacted_items.append(item_id)

    return recommendations


