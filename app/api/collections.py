from app.database import get_session, Learner
from app.services import bricks, auth
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session


router = APIRouter(prefix="/collections", tags=["Collections"])

@router.get("")
async def get_user_collections(
    current_learner: Learner = Depends(auth.decode_token_to_get_learner), 
    session: Session = Depends(get_session)
):
    return bricks.get_user_collections(session, current_learner.id)
