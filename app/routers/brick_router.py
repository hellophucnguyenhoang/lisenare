import random
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlmodel import Session

from app.config import settings
from app.database import Learner, get_session
from app.schemas import (
    BrickAudioData,
    BrickAudioPage,
    BrickCreateRequest,
    BrickPage,
    BrickRead,
    BrickSort,
    BrickStatus,
    BrickUpdate,
    OverrideBrickRequest,
)
from app.services import (
    auth_service,
    brick_override_service,
    brick_service,
    broken_brick_report_service,
)
from utils import file_utils
from utils.form_utils import JsonFormBody

router = APIRouter(prefix="/bricks", tags=["Bricks"])


@router.get("/pending")
def get_pending_bricks(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_id: int,
    status: BrickStatus | None = None,
    sort_by: BrickSort = BrickSort.RECOMMENDED,
    limit: int = 20,
    page: int = 1,
) -> BrickPage:
    offset = (page - 1) * limit

    bricks_list = brick_service.get_pending_bricks(
        session, learner.id, [collection_id], status, sort_by, offset, limit
    )

    total_count = brick_service.count_pending_bricks(
        session, learner.id, [collection_id], status
    )

    return BrickPage(items=bricks_list, total=total_count)


@router.get("/fsrs", response_model=BrickRead | None)
def get_brick_fsrs(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_ids: Annotated[list[int] | None, Query()] = None,
):
    return brick_service.get_brick_fsrs(
        session=session,
        learner_id=learner.id,
        collection_ids=collection_ids,
    )


@router.get("/audio")
def get_brick_audios(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_ids: Annotated[list[int] | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=100)] = 20,
    shuffle_page: Annotated[bool, Query()] = False,
) -> BrickAudioPage:
    print(f"{collection_ids = }")
    pending_bricks = brick_service.get_pending_bricks(
        session=session,
        learner_id=learner.id,
        collection_ids=collection_ids,
        offset=offset,
        limit=limit,
    )
    if shuffle_page:
        random.shuffle(pending_bricks)

    total = brick_service.count_pending_bricks(
        session=session,
        learner_id=learner.id,
        collection_ids=collection_ids,
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


@router.get("/by-id/{brick_id}", response_model=BrickRead)
def get_brick_details(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_optional_learner)
    ],
    brick_id: int,
):
    learner_id = learner.id if learner else None
    return brick_service.get_brick(session, brick_id, learner_id)


@router.post("", response_model=BrickRead)
async def create_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    audio_file: Annotated[UploadFile, File()],
    request_data: Annotated[
        BrickCreateRequest, Depends(JsonFormBody(BrickCreateRequest))
    ],
):
    creator_id = learner.id
    learner_audio_path, _ = await file_utils.save_cloud_upload_file(
        file=audio_file,
        base_dir=settings.brick_audios_folder,
        filename_prefix=f"ln{creator_id}rec",
    )
    return brick_service.create_brick(
        session, request_data, creator_id, learner_audio_path
    )


@router.post("/override", status_code=status.HTTP_201_CREATED)
def save_brick_override(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    payload: OverrideBrickRequest,
) -> Response:
    brick_override_service.save_override_for_brick(
        session,
        learner_id=learner.id,
        brick_id=payload.brick_id,
        collection_name=payload.collection_name,
    )
    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/report/{brick_id}", status_code=status.HTTP_201_CREATED)
def report_broken_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
    response: Response,  # Response Injection to change the status code
    description: str | None = None,
):
    is_created = broken_brick_report_service.save_report(
        session, learner.id, brick_id, description
    )

    if not is_created:
        response.status_code = status.HTTP_204_NO_CONTENT

    return Response(status_code=response.status_code)


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
async def update_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
    brick_update: Annotated[BrickUpdate, Depends(JsonFormBody(BrickUpdate))],
    audio_file: Annotated[UploadFile | None, File()] = None,
):
    learner_audio_path = None
    if audio_file:
        learner_audio_path, _ = await file_utils.save_cloud_upload_file(
            file=audio_file,
            base_dir=settings.brick_audios_folder,
            filename_prefix=f"ln{learner.id}upd",
        )

    return brick_service.update_brick(
        session=session,
        brick_id=brick_id,
        brick_update=brick_update,
        learner_id=learner.id,
        target_audio_path=learner_audio_path,
    )


@router.delete("/{brick_id}")
def delete_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
):
    result = brick_service.delete_brick(session, learner.id, brick_id)

    # Complete deletion of the entity -> 204 No Content
    if result == "BRICK_DELETED":
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Ownership shifted or personal record dropped -> 200 OK
    return Response(status_code=status.HTTP_200_OK)
