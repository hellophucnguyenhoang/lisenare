from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, Form, UploadFile, File, Query
from sqlmodel import Session
from typing import Annotated
from pathlib import Path
from datetime import datetime, timezone
import shutil

from app.database import get_session
from app.services import auth_service, brick_service
from app.schemas import BrickUpdate, BrickRead, BrickCreate, BrickLearnRead
from app.database import Learner
from app.config import settings


router = APIRouter(prefix="/bricks", tags=["Bricks"])


@router.patch(
    "/{brick_id}",
    response_model=BrickRead,
    summary="Update a brick or create/update a personal override",
    description="""
If the learner is the creator, the original brick is updated and returned.

If not, a personal override is created or updated instead.
The original brick remains unchanged, 
and a brick with the edited native_text if requested is return instead.
""",
)
def update_brick(
    brick_id: int,
    brick_update: BrickUpdate,
    current_learner: Learner = Depends(
        auth_service.decode_token_to_get_learner
    ),
    session: Session = Depends(get_session),
):
    return brick_service.update_brick(
        session=session,
        brick_id=brick_id,
        brick_update=brick_update,
        learner_id=current_learner.id,
    )


@router.post("/", response_model=BrickRead)
def create_brick(
    audio_file: Annotated[UploadFile, File()],
    native_text: Annotated[str, Form()],
    target_text: Annotated[str, Form()],
    is_public: Annotated[bool, Form()] = True,
    current_learner: Learner = Depends(
        auth_service.decode_token_to_get_learner
    ),
    session: Session = Depends(get_session),
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
        target_audio_uri=target_audio_uri,  # e.g. "user_1_audio.wav"
    )
    return brick_service.create_brick(session, brick_create)


@router.get("/audio/{filename}")
def get_brick_audio(filename: str):
    return StreamingResponse(
        brick_service.iter_audio_file(filename), media_type="audio/wav"
    )


@router.get("/by-id/{brick_id}", response_model=BrickRead)
def get_brick(brick_id: int, session: Session = Depends(get_session)):
    return brick_service.get_brick(session, brick_id)


@router.get("/random", response_model=BrickRead)
def get_random_brick(
    collection_ids: list[int] | None = Query(default=None),
    current_learner: Learner = Depends(
        auth_service.decode_token_to_get_learner
    ),
    session: Session = Depends(get_session),
):
    print(f"collection_ids: {collection_ids}")
    return brick_service.get_random_brick(
        session=session,
        learner_id=current_learner.id,
        collection_ids=collection_ids,
    )


@router.get("/fsrs", response_model=BrickRead)
def get_brick_fsrs(
    collection_ids: list[int] | None = Query(default=None),
    current_learner: Learner = Depends(
        auth_service.decode_token_to_get_learner
    ),
    session: Session = Depends(get_session),
):
    print(f"collection_ids: {collection_ids}")
    return brick_service.get_brick_fsrs(
        session=session,
        learner_id=current_learner.id,
        collection_ids=collection_ids,
    )


@router.get("/learn/{collection_id}", response_model=BrickLearnRead)
def get_brick_in_collection_learn(
    collection_id: int,
    brick_order: int = Query(default=1, ge=1),
    current_learner: Learner = Depends(
        auth_service.decode_token_to_get_learner
    ),
    session: Session = Depends(get_session),
):
    return brick_service.get_brick_in_collection_learn(
        session=session,
        learner_id=current_learner.id,
        collection_id=collection_id,
        brick_order=brick_order,
    )


@router.post("/report/{filename}")
def append_broken_audio_file(filename: str):
    REPORT_FILE = Path(settings.broken_report_file)
    if REPORT_FILE.exists():
        if filename in REPORT_FILE.read_text():
            return {"status": "exists", "message": "Already reported."}
    with REPORT_FILE.open("a") as f:
        f.write(f"{filename}|{datetime.now(timezone.utc)}\n")
    return {"status": "success", "message": f"Reported {filename}"}
