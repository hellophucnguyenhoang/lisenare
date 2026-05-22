"""
The reason why do we have a separate auth group of endpoint here
while it's mostly do things with account is because
this authentication can be a third-party application.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app import security
from app.database import get_session
from app.schemas import Token
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login_for_access_token(
    session: Annotated[Session, Depends(get_session)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    account = auth_service.authenticate_account(
        session, form_data.username, form_data.password
    )
    data = {"sub": str(account.learner_id), "username": account.username}
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)
