from app.database import get_session
from app.services import bricks
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.config import settings
from pathlib import Path
from datetime import datetime, timezone

router = APIRouter(prefix="/bricks", tags=["Bricks"])

@router.get("/by-id/{id}")
async def get_brick(id: int, session: Session = Depends(get_session)):
    return bricks.get_brick(session, id)

@router.get("/audio/{filename}")
def get_brick_audio(filename: str):
    return StreamingResponse(bricks.iter_audio_file(filename), media_type="audio/wav")

@router.get("/random")
async def get_random_brick(session: Session = Depends(get_session)):
    return bricks.get_random_brick(session)

@router.post("/report/{filename}")
def append_broke_audio_file(filename: str):
    with open("reported_broken_audio_files.txt", "a") as f:
        f.write(f"{filename}|{datetime.now(timezone.utc)}\n")
    return {"status": "success", "message": f"File '{filename}' reported."}
