# app/api/auth.py
from fastapi import APIRouter, Depends
from sqlmodel import Session
from fastapi.security import OAuth2PasswordRequestForm
from app.database import get_session
from app.services import auth as auth_service
from app.schemas import Token

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=Token)
def login_api(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    return auth_service.login_for_access_token(session, form_data.username, form_data.password)
