# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.services import readings as reading_service
from app.schemas import RecommendItemRequest, RecommendItemResponse, UserStateRead
import numpy as np
from stable_baselines3 import PPO

router = APIRouter(prefix="/recommendation", tags=["Recommendations"])


MODEL_PATH = "./ai_models/ppo_user_sim.zip"
model = PPO.load(MODEL_PATH)

OBS_DIM = 384
USER_EMBEDDINGS = {
    "phuc": np.random.randn(OBS_DIM).astype(np.float32)
}

USER_STATE = {
    "phuc": UserStateRead(user_id=1, item_ids="this is assumed to change", id=1)
}

@router.post("/recommend", response_model=RecommendItemResponse)
def recommend_api(req: RecommendItemRequest, session: Session = Depends(get_session)):

    # Get user's observation vector
    obs = USER_EMBEDDINGS.get(req.username)
    if obs is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Predict the best item for this user
    action, _ = model.predict(obs, deterministic=True)
    item_id = int(action)
    recommended_reading = reading_service.get_full_reading_by_id(session, item_id)

    # update user history
    USER_EMBEDDINGS[req.username] = 0.5 * USER_EMBEDDINGS[req.username] + np.random.randn(OBS_DIM).astype(np.float32)

    user_state = USER_STATE[req.username]
    # if user_state.item_ids:
    #     user_state.item_ids += f",{item_id}"
    # else:
    #     user_state.item_ids = str(item_id)
    user_state.id += 1
    USER_STATE[req.username] = user_state

    return RecommendItemResponse(user_state=user_state, item=recommended_reading)

