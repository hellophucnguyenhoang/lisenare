from app.database import get_session
from app.services import bricks
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.config import settings
from pathlib import Path

router = APIRouter(prefix="/bricks", tags=["Bricks"])

@router.get("/brick/{id}")
async def get_brick(id: int, session: Session = Depends(get_session)):
    return bricks.get_brick(session, id)

@router.get("/audio/{filename}")
def get_brick_audio(filename: str):
    return StreamingResponse(bricks.iter_audio_file(filename), media_type="audio/wav")
