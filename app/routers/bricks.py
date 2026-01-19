from app.database import get_session
from app.services import auth_service, brick_service
from app.schemas import BrickUpdate, BrickRead, BrickCreate
from app.database import Learner
from app.config import settings
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlmodel import Session
from typing import Annotated
from pathlib import Path
from datetime import datetime, timezone
import shutil

router = APIRouter(prefix="/bricks", tags=["Bricks"])

@router.get("/audio/{filename}")
def get_brick_audio(filename: str):
    return StreamingResponse(brick_service.iter_audio_file(filename), media_type="audio/wav")

@router.get("/{brick_id}", response_model=BrickRead)
async def get_brick(brick_id: int, session: Session = Depends(get_session)):
    return brick_service.get_brick(session, brick_id)

@router.post("/report/{filename}")
async def append_broke_audio_file(filename: str):
    with open("reported_broken_audio_files.txt", "a") as f:
        f.write(f"{filename}|{datetime.now(timezone.utc)}\n")
    return {"status": "success", "message": f"File '{filename}' reported."}

@router.get("/random/{collection_id}", response_model=BrickRead)
async def get_random_brick(
    collection_id: int,
    current_learner: Learner = Depends(auth_service.decode_token_to_get_learner), 
    session: Session = Depends(get_session)
):
    return brick_service.get_random_brick(session, current_learner.id, collection_id)

@router.patch("/{brick_id}", response_model=BrickRead)
async def update_brick(
    brick_id: int,
    brick_update: BrickUpdate,
    current_learner: Learner = Depends(auth_service.decode_token_to_get_learner),
    session: Session = Depends(get_session),
):
    return brick_service.update_brick(
        session=session,
        brick_id=brick_id,
        brick_update=brick_update,
        user_id=current_learner.id,
    )

@router.post("/", response_model=BrickRead)
async def create_brick(
    audio_file: Annotated[UploadFile, File()],
    native_text: Annotated[str, Form()],
    target_text: Annotated[str, Form()],
    is_public: Annotated[bool, Form()] = True,
    current_learner: Learner = Depends(auth_service.decode_token_to_get_learner),
    session: Session = Depends(get_session)
):
    UPLOAD_DIR = Path(settings.brick_folder)
    creator_id = current_learner.id
    target_audio_uri = f"user_{creator_id}_{audio_file.filename}"
    file_path = UPLOAD_DIR / target_audio_uri
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(audio_file.file, buffer)
    brick_create = BrickCreate(
        native_text=native_text,
        target_text=target_text,
        creator_id=creator_id,
        is_public=is_public,
        target_audio_uri=target_audio_uri # e.g. "user_1_audio.wav"
    )
    return brick_service.create_brick(session, brick_create)
