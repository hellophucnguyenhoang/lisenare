from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import Token
from sqlmodel import Session
from app.database import get_session
from app.services import account_service
from app import security
from app.schemas import LearnerAccountCreate

router = APIRouter(prefix="/accounts", tags=["Accounts"])

@router.post("/register", response_model=Token)
def register_for_access_token(
    learner_account_create: LearnerAccountCreate, 
    session: Session = Depends(get_session)
) -> Token:
    account = account_service.create_learner_account(session, learner_account_create)
    data = {
        "sub": str(account.learner_id),
        "username": account.username
    }
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)
