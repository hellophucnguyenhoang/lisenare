"""
The reason why do we have a separate auth group of endpoint here 
while it's mostly do things with account is because 
this authentication can be a third-party application.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.schemas import Token
from sqlmodel import Session
from app.database import get_session
from app.services import auth
from app import security

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    session: Session = Depends(get_session)
) -> Token:
    account = auth.authenticate_account(session, form_data.username, form_data.password)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    data = {
        "sub": str(account.learner_id),
        "username": account.username
    }
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)
