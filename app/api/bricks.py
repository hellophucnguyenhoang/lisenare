from app.database import get_session
from app.services import bricks, auth
from app.schemas import BrickUpdate
from app.database import Learner
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from datetime import datetime, timezone

router = APIRouter(prefix="/bricks", tags=["Bricks"])

@router.get("/audio/{filename}")
def get_brick_audio(filename: str):
    return StreamingResponse(bricks.iter_audio_file(filename), media_type="audio/wav")

@router.get("/{brick_id}")
async def get_brick(brick_id: int, session: Session = Depends(get_session)):
    return bricks.get_brick(session, brick_id)

@router.post("/report/{filename}")
async def append_broke_audio_file(filename: str):
    with open("reported_broken_audio_files.txt", "a") as f:
        f.write(f"{filename}|{datetime.now(timezone.utc)}\n")
    return {"status": "success", "message": f"File '{filename}' reported."}

@router.get("/random/{collection_id}")
async def get_random_brick(
    collection_id: int,
    current_learner: Learner = Depends(auth.decode_token_to_get_learner), 
    session: Session = Depends(get_session)
):
    return bricks.get_random_brick(session, current_learner.id, collection_id)

@router.patch("/{brick_id}")
async def update_brick(
    brick_id: int,
    brick_update: BrickUpdate,
    current_learner: Learner = Depends(auth.decode_token_to_get_learner),
    session: Session = Depends(get_session),
):
    return bricks.update_brick(
        session=session,
        brick_id=brick_id,
        brick_update=brick_update,
        user_id=current_learner.id,
    )
