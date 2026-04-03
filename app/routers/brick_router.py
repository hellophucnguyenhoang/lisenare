from fastapi.responses import StreamingResponse
from fastapi import (
    APIRouter,
    Depends,
    Form,
    UploadFile,
    File,
    Query,
    status,
    HTTPException,
)
from sqlmodel import Session
from typing import Annotated
from pathlib import Path
from datetime import datetime, timezone
import shutil
import json
from pydantic import ValidationError

from app.database import get_session
from app.services import auth_service, brick_service
from app.schemas import (
    BrickUpdate,
    BrickRead,
    BrickCreate,
    BrickLearnRead,
    BrickCreateRequest,
    StatusResponse,
    UnitType,
)
from app.database import Learner, BrickMetadata, BrickMetadataGrammarPoint
from app.config import settings


router = APIRouter(prefix="/bricks", tags=["Bricks"])


@router.patch(
    "/{brick_id}",
    response_model=BrickRead,
    summary="Update a brick or create/update a personal override",
    description="""
If the learner is the creator of the brick, 
the original brick is updated and returned.

If not, a personal override of the brick is created or updated instead. 
The original brick remains unchanged, 
and a brick with the edited information is return.

Non-author learners can only edit native_text field.
""",
)
def update_brick(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_to_get_learner)
    ],
    brick_id: int,
    brick_update: BrickUpdate,
):
    return brick_service.update_brick(
        session=session,
        brick_id=brick_id,
        brick_update=brick_update,
        learner_id=current_learner.id,
    )


@router.post("", response_model=BrickRead)
def create_brick(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_to_get_learner)
    ],
    audio_file: Annotated[UploadFile, File()],
    brick_data: Annotated[
        str,
        Form(description="A serialized string of a BrickCreateRequest object"),
    ],
):
    try:
        data_dict = json.loads(brick_data)
        request_data = BrickCreateRequest.model_validate(data_dict)
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dữ liệu không hợp lệ: {str(e)}",
        )

    UPLOAD_DIR = Path(settings.brick_folder)
    creator_id = current_learner.id
    target_audio_uri = f"learner_{creator_id}_{audio_file.filename}"
    file_path = UPLOAD_DIR / target_audio_uri
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        return brick_service.create_brick(
            session, request_data, creator_id, str(file_path)
        )
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A brick with this target text already exists.",
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/audio/{filename}")
def get_brick_audio(filename: str):
    """
    DEPRECATED due to static files. See app/main.py
    """
    return StreamingResponse(
        brick_service.iter_audio_file(filename), media_type="audio/wav"
    )


@router.get("/by-id/{brick_id}", response_model=BrickRead)
def get_brick(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_to_get_learner)
    ],
    brick_id: int,
):
    return brick_service.get_brick(session, brick_id, current_learner.id)


@router.get("/fsrs", response_model=BrickRead)
def get_brick_fsrs(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_to_get_learner)
    ],
    collection_ids: Annotated[list[int] | None, Query()] = None,
):
    brick_read = brick_service.get_brick_fsrs(
        session=session,
        learner_id=current_learner.id,
        collection_ids=collection_ids,
    )
    if brick_read is None:
        print("brick read None")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Haven't had any sentence to practice yet.",
        )
    return brick_read


@router.get("/learn/{collection_id}", response_model=BrickLearnRead)
def get_brick_in_collection_learn(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_to_get_learner)
    ],
    collection_id: int,
    brick_order: Annotated[int, Query(ge=1)] = 1,
):
    brick_learn = brick_service.get_brick_in_collection_learn(
        session=session,
        learner_id=current_learner.id,
        collection_id=collection_id,
        brick_order=brick_order,
    )
    return brick_learn


@router.post("/report/{filename}", response_model=StatusResponse)
def append_broken_audio_file(filename: str, description: str | None = None):
    REPORT_FILE = Path(settings.broken_report_file)
    if REPORT_FILE.exists():
        if filename in REPORT_FILE.read_text():
            return {"status": "exists", "message": "Already reported."}
    with REPORT_FILE.open("a") as f:
        clean_desc = description.replace("|", " ").replace("\n", " ")
        f.write(f"{filename}|{clean_desc}|{datetime.now(timezone.utc)}\n")
    return {"status": "success", "message": f"Reported {filename}"}
