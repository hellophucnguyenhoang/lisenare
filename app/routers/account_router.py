from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import security
from app.schemas import Token, ChangePasswordRequest
from app.database import get_session, Learner
from app.services import account_service, auth_service
from app.schemas import LearnerAccountCreate

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("", response_model=Token)
def create_account(
    learner_account_create: LearnerAccountCreate,
    session: Session = Depends(get_session),
) -> Token:
    account = account_service.create_learner_account(
        session, learner_account_create
    )
    data = {"sub": str(account.learner_id), "username": account.username}
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)


@router.patch("/me/password", response_model=Token)
def update_account_password(
    change_password_request: ChangePasswordRequest,
    learner: Learner = Depends(auth_service.decode_token_to_get_learner),
    session: Session = Depends(get_session),
) -> Token:
    account = account_service.change_learner_account_password(
        session,
        learner_id=learner.id,
        old_password=change_password_request.old_password,
        new_password=change_password_request.new_password,
    )
    data = {"sub": str(account.learner_id), "username": account.username}
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)
