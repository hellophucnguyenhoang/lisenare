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
    BrickCreateRequest,
    BrickListeningData,
    BrickListeningPage,
    BrickPage,
    BrickRead,
    BrickSort,
    BrickStatus,
    BrickUpdate,
)
from app.services import (
    auth_service,
    brick_service,
)
from utils import file_utils
from utils.form_utils import JsonFormBody

router = APIRouter(prefix="/bricks", tags=["Bricks"])


@router.get("")
def get_bricks(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_ids: Annotated[list[int] | None, Query()] = None,
    status: BrickStatus | None = None,
    sort_by: BrickSort = BrickSort.NEWEST,
    limit: int = 20,
    page: int = 1,
) -> BrickPage:
    offset = (page - 1) * limit

    bricks_list = brick_service.get_bricks(
        session=session,
        creator_id=creator.id,
        collection_ids=collection_ids,
        status=status,
        sort_by=sort_by,
        offset=offset,
        limit=limit,
    )

    total_count = brick_service.count_bricks(
        session=session,
        creator_id=creator.id,
        collection_ids=collection_ids,
        status=status,
    )

    return BrickPage(items=bricks_list, total=total_count)


@router.get("/next", response_model=BrickRead | None)
def get_next_brick(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_ids: Annotated[list[int] | None, Query()] = None,
):
    return brick_service.get_next_brick(
        session=session,
        creator_id=creator.id,
        collection_ids=collection_ids,
    )


@router.get("/listening")
def get_listening_bricks(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_ids: Annotated[list[int] | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=100)] = 20,
    shuffle_page: Annotated[bool, Query()] = False,
) -> BrickListeningPage:
    print(f"{collection_ids = }")
    bricks = brick_service.get_bricks(
        session=session,
        creator_id=creator.id,
        collection_ids=collection_ids,
        offset=offset,
        limit=limit,
    )
    if shuffle_page:
        random.shuffle(bricks)

    total = brick_service.count_bricks(
        session=session,
        creator_id=creator.id,
        collection_ids=collection_ids,
    )
    return BrickListeningPage(
        items=[
            BrickListeningData(
                audio_path=brick.target_audio_path,
                target_text=brick.target_text,
                native_text=brick.native_text,
            )
            for brick in bricks
        ],
        offset=offset,
        limit=limit,
        total=total,
    )


@router.get("/exists")
def check_brick_exists(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    target_text: str,
) -> bool:
    return brick_service.check_brick_exists(
        session=session,
        creator_id=creator.id,
        target_text=target_text,
    )


@router.post("", response_model=BrickRead)
async def create_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    target_audio_file: Annotated[UploadFile, File()],
    request_data: Annotated[
        BrickCreateRequest, Depends(JsonFormBody(BrickCreateRequest))
    ],
):
    creator_id = learner.id
    target_audio_path, _ = await file_utils.save_upload_file(
        file=target_audio_file,
        base_dir=settings.learner_audios_folder,
        sub_dir=f"learner-{creator_id}",
        filename_prefix="brick",
    )
    return brick_service.create_brick(
        session=session,
        request_data=request_data,
        creator_id=creator_id,
        target_audio_path=target_audio_path,
    )


@router.patch("/{brick_id}", response_model=BrickRead)
async def update_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
    brick_update: Annotated[BrickUpdate, Depends(JsonFormBody(BrickUpdate))],
    target_audio_file: Annotated[UploadFile | None, File()] = None,
):
    target_audio_path = None
    if target_audio_file:
        target_audio_path, _ = await file_utils.save_upload_file(
            file=target_audio_file,
            base_dir=settings.learner_audios_folder,
            sub_dir=f"learner-{learner.id}",
            filename_prefix="brick",
        )

    return brick_service.update_brick(
        session=session,
        brick_id=brick_id,
        brick_update=brick_update,
        creator_id=learner.id,
        target_audio_path=target_audio_path,
    )


@router.delete("/{brick_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
) -> Response:
    brick_service.delete_brick(session, learner.id, brick_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
