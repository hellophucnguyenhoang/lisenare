import json
import random
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
from pydantic import ValidationError
from sqlmodel import Session

from app.config import settings
from app.database import Learner, get_session
from app.schemas import (
    BrickAudioData,
    BrickAudioPage,
    BrickCreateRequest,
    BrickLearnRead,
    BrickRead,
    BrickUpdate,
    StatusResponse,
    StatusResponseType,
)
from app.services import (
    auth_service,
    brick_service,
    broken_brick_report_service,
)
from utils import file_utils

router = APIRouter(prefix="/bricks", tags=["Bricks"])


@router.get("/fsrs", response_model=BrickRead)
def get_brick_fsrs(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_ids: Annotated[list[int] | None, Query()] = None,
):
    brick = brick_service.get_brick_fsrs(
        session=session,
        learner_id=learner.id,
        collection_ids=collection_ids,
    )
    if brick is None:
        print("Brick is None")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Haven't had any sentence to practice yet.",
        )
    return brick


@router.get("/audio")
def get_brick_audios(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    group_names: Annotated[list[str] | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=100)] = 20,
    shuffle_page: Annotated[bool, Query()] = False,
) -> BrickAudioPage:
    print(f"{group_names = }")
    pending_bricks = brick_service.get_pending_bricks(
        session=session,
        learner_id=learner.id,
        group_names=group_names,
        offset=offset,
        limit=limit,
    )
    if shuffle_page:
        random.shuffle(pending_bricks)
    total = brick_service.count_pending_bricks(
        session=session,
        learner_id=learner.id,
        group_names=group_names,
    )
    return BrickAudioPage(
        items=[
            BrickAudioData(
                audio_path=brick.target_audio_path,
                target_text=brick.target_text,
                native_text=brick.native_text,
            )
            for brick in pending_bricks
        ],
        offset=offset,
        limit=limit,
        total=total,
    )


@router.get("/check-exists", response_model=dict)
def check_target_text_exists(
    target_text: str, session: Session = Depends(get_session)
):
    # Search for any brick with the exact target_text
    exists = brick_service.check_target_text_exists(session, target_text)
    return {"exists": exists}


@router.get("/public/by-id/{brick_id}", response_model=BrickRead)
def get_public_brick(
    session: Annotated[Session, Depends(get_session)],
    brick_id: int,
):
    # Pass learner_id=None to indicate guest access
    return brick_service.get_brick(session, brick_id, learner_id=None)


@router.get("/by-id/{brick_id}", response_model=BrickRead)
def get_private_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
):
    return brick_service.get_brick(session, brick_id, learner.id)


@router.get("/learn/{collection_id}", response_model=BrickLearnRead)
def get_brick_in_collection_learn(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_id: int,
    brick_order: Annotated[int, Query(ge=1)] = 1,
):
    brick_learn = brick_service.get_brick_in_collection_learn(
        session=session,
        learner_id=learner.id,
        collection_id=collection_id,
        brick_order=brick_order,
    )
    return brick_learn


@router.post("", response_model=BrickRead)
async def create_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
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

    creator_id = learner.id
    learner_audio_path, _ = await file_utils.save_upload_file(
        file=audio_file,
        base_dir=settings.brick_audios_folder,
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


@router.post("/report/{filename}")
def report_broken_audio(
    session: Annotated[Session, Depends(get_session)],
    filename: str,
    description: str | None = None,
) -> StatusResponse:
    result = broken_brick_report_service.save_report(
        session, filename, description
    )
    if result is None:
        return StatusResponse(
            status=StatusResponseType.EXISTED, message="Already reported."
        )

    return StatusResponse(
        status=StatusResponseType.SUCCESS, message=f"Reported {filename}"
    )


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
    learner: Annotated[
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
        learner_id=learner.id,
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
        "status": StatusResponseType.SUCCESS,
        "message": message,
    }
