from app.database import get_session
from app.services import bricks
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.schemas import BrickUpdate
from datetime import datetime, timezone

router = APIRouter(prefix="/bricks", tags=["Bricks"])

@router.get("/audio/{filename}")
def get_brick_audio(filename: str):
    return StreamingResponse(bricks.iter_audio_file(filename), media_type="audio/wav")

@router.get("/by-id/{id}")
async def get_brick(id: int, session: Session = Depends(get_session)):
    return bricks.get_brick(session, id)

@router.get("/random")
async def get_random_brick(collection_id: int = 1, session: Session = Depends(get_session)):
    return bricks.get_random_brick(session, collection_id)

@router.post("/report/{filename}")
def append_broke_audio_file(filename: str):
    with open("reported_broken_audio_files.txt", "a") as f:
        f.write(f"{filename}|{datetime.now(timezone.utc)}\n")
    return {"status": "success", "message": f"File '{filename}' reported."}

@router.get("/collections")
async def get_user_collections(user_id: int = 1, session: Session = Depends(get_session)):
    return bricks.get_user_collections(session, user_id)

@router.patch("/{brick_id}")
def update_brick(
    user_id: int,
    brick_id: int,
    brick_update: BrickUpdate,
    session: Session = Depends(get_session),
):
    return bricks.update_brick(
        session=session,
        brick_id=brick_id,
        brick_update=brick_update,
        user_id=user_id,
    )
