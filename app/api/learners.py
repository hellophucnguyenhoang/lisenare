from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.schemas import Token
from sqlmodel import Session
from app.database import get_session, Learner
from app.services import auth
from app import security

router = APIRouter(prefix="/learners", tags=["Learners"])

@router.get("/me")
async def get_learner_me(learner: Learner = Depends(auth.decode_token_to_get_learner)):
    return learner
