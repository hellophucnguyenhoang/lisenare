from . import account_service, learner_service
from app import security
from sqlmodel import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.database import get_session, Account, Learner
from jwt import InvalidTokenError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def authenticate_account(session: Session, username: str, password: str) -> Account:
    account = account_service.get_account_by_username(session, username)
    if not account or not security.verify_password(password, account.hashed_password):
        return None
    return account

async def decode_token_to_get_learner(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> Learner:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = security.decode_access_token(token)
        learner_id = payload.sub
        if not learner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found learner_id in the sub of the token")
    except InvalidTokenError:
        raise credentials_exception
    learner = learner_service.get_learner_by_id(session, learner_id)
    if not learner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found for learner_id")
    return learner