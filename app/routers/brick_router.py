import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlmodel import Session

from app.config import settings
from app.database import Learner, get_session
from app.schemas import (
    BrickCreateRequest,
    BrickLearnRead,
    BrickRead,
    BrickUpdate,
    StatusResponse,
    StatusType,
)
from app.services import auth_service, brick_service
from utils import file_utils

router = APIRouter(prefix="/bricks", tags=["Bricks"])


@router.get("/fsrs", response_model=BrickRead)
def get_brick_fsrs(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
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


@router.get("/audio")
def get_brick_audios(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    group_names: Annotated[list[str] | None, Query()] = None,
):
    print(f"{group_names = }")
    pending_bricks = brick_service.get_pending_bricks(
        session=session,
        learner_id=learner.id,
        group_names=group_names,
    )
    audio_uris = [brick.target_audio_uri for brick in pending_bricks]
    return audio_uris


@router.get("/audio/{filename}")
def get_brick_audio(filename: str):
    """
    DEPRECATED due to static files. See app/main.py
    """
    return StreamingResponse(
        brick_service.iter_audio_file(filename), media_type="audio/wav"
    )


@router.get("/check-exists", response_model=dict)
def check_target_text_exists(
    target_text: str, session: Session = Depends(get_session)
):
    # Search for any brick with the exact target_text
    exists = brick_service.check_target_text_exists(session, target_text)

    return {"exists": exists}


@router.get("/by-id/{brick_id}", response_model=BrickRead)
def get_brick(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
):
    return brick_service.get_brick(session, brick_id, current_learner.id)


@router.get("/learn/{collection_id}", response_model=BrickLearnRead)
def get_brick_in_collection_learn(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
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


@router.post("", response_model=BrickRead)
async def create_brick(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
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

    creator_id = current_learner.id
    learner_audio_path, _ = await file_utils.save_upload_file(
        file=audio_file,
        base_dir=settings.brick_folder,
        filename_prefix=f"ln{creator_id}rec",
    )
    print(f"{learner_audio_path = }")
    try:
        return brick_service.create_brick(
            session, request_data, creator_id, learner_audio_path
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


@router.post("/report/{filename}", response_model=StatusResponse)
def append_broken_audio_file(filename: str, description: str | None = None):
    REPORT_FILE = Path(settings.broken_report_file)
    if REPORT_FILE.exists():
        if filename in REPORT_FILE.read_text():
            return {"status": "exists", "message": "Already reported."}
    with REPORT_FILE.open("a") as f:
        clean_desc = description.replace("|", " ").replace("\n", " ")
        f.write(f"{filename}|{clean_desc}|{datetime.now(timezone.utc)}\n")
    return {"status": StatusType.SUCCESS, "message": f"Reported {filename}"}


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

For creativity encouragement, target_text is globally unique, and
non-author learners can only override native_text field.
""",
)
def update_brick(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
    brick_update: BrickUpdate,
):
    # TODO: Create a complete new brick when the target text is new
    # TODO: Let user update target audio in the override version
    return brick_service.update_brick(
        session=session,
        brick_id=brick_id,
        brick_update=brick_update,
        learner_id=current_learner.id,
    )


@router.delete("/{brick_id}", response_model=StatusResponse)
def delete_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
):
    result = brick_service.delete_brick(session, learner.id, brick_id)

    message = (
        "Original brick and all metadata deleted."
        if result == "BRICK_DELETED"
        else "Your personal override for this brick was removed."
    )

    return {
        "status": StatusType.SUCCESS,
        "message": message,
    }
