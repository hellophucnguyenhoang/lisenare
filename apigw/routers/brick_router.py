import random
from typing import Annotated, Literal

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

from config import logger
from constants import LEARNER_AUDIOS_DIR
from database import Learner, get_session
from schemas import (
    AddBrickRequest,
    AddIslandRequest,
    AddIslandResult,
    BrickCreateRequest,
    BrickDetailRead,
    BrickListeningData,
    BrickListeningPage,
    BrickPage,
    BrickRead,
    BrickReportCreate,
    BrickSort,
    BrickStatus,
    BrickUpdate,
)
from services import (
    audio_cache_service,
    auth_service,
    brick_service,
)
from utils import file_utils
from utils.form_utils import JsonFormBody
from utils.tag_utils import clean_tags

router = APIRouter(prefix="/bricks", tags=["Bricks"])


@router.get("")
def get_bricks(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    island_ids: Annotated[list[int] | None, Query()] = None,
    status: BrickStatus | None = None,
    kind: Literal["word", "sentence"] | None = None,
    tags: Annotated[list[str] | None, Query()] = None,
    sort_by: BrickSort = BrickSort.NEWEST,
    limit: int = 20,
    page: int = 1,
) -> BrickPage:
    offset = (page - 1) * limit

    cleaned_tags = clean_tags(tags) if tags else None

    bricks_list = brick_service.get_bricks(
        session=session,
        creator_id=creator.id,
        island_ids=island_ids,
        status=status,
        kind=kind,
        tags=cleaned_tags or None,
        sort_by=sort_by,
        offset=offset,
        limit=limit,
    )

    total_count = brick_service.count_bricks(
        session=session,
        creator_id=creator.id,
        island_ids=island_ids,
        status=status,
        kind=kind,
        tags=cleaned_tags or None,
    )

    return BrickPage(items=bricks_list, total=total_count)


@router.get("/next", response_model=BrickRead | None)
def get_next_brick(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    island_ids: Annotated[list[int] | None, Query()] = None,
    brick_id: int | None = None,
):
    return brick_service.get_next_brick(
        session=session,
        creator_id=creator.id,
        island_ids=island_ids,
        brick_id=brick_id,
        retrieval_lang=creator.retrieval_lang,
    )


@router.get("/listening")
def get_listening_bricks(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    island_ids: Annotated[list[int] | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=100)] = 10,
    shuffle_page: Annotated[bool, Query()] = False,
) -> BrickListeningPage:
    logger.info(f"{island_ids = }")
    bricks = brick_service.get_bricks(
        session=session,
        creator_id=creator.id,
        island_ids=island_ids,
        offset=offset,
        limit=limit,
    )
    if shuffle_page:
        random.shuffle(bricks)

    total = brick_service.count_bricks(
        session=session,
        creator_id=creator.id,
        island_ids=island_ids,
    )
    return BrickListeningPage(
        items=[
            BrickListeningData(
                audio_path=audio_cache_service.get_brick_audio_url(
                    session=session,
                    brick_id=brick.id,
                    learner_id=creator.id,
                ),
                target_text=brick.target_text,
                native_text=brick.native_text,
                target_pron=brick.target_pron,
                context=brick.context,
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


@router.get("/recommended/{session_id}")
def get_recommended_bricks(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    session_id: str,
    page_size: int = 5,
) -> BrickPage:
    bricks = brick_service.get_recommended_bricks(
        session,
        session_id,
        page_size,
        retrieval_lang=learner.retrieval_lang,
    )
    if len(bricks) < page_size:
        exclude_ids = [b.id for b in bricks if b.id is not None]
        redis = brick_service.get_redis_client()
        cache_key = f"recommended_bricks:{session_id}"
        exclude_ids = list(
            set(exclude_ids) | {int(bid) for bid in redis.smembers(cache_key)}
        )
        additional_bricks = brick_service.get_random_bricks(
            session,
            limit=page_size - len(bricks),
            exclude_ids=exclude_ids,
            retrieval_lang=learner.retrieval_lang,
        )
        if additional_bricks:
            redis.sadd(
                cache_key,
                *[b.id for b in additional_bricks if b.id is not None],
            )
            redis.expire(cache_key, 3600)
            bricks.extend(additional_bricks)

    return BrickPage(items=bricks, total=len(bricks))


@router.post("/add-from/{brick_id}", response_model=BrickRead)
def add_brick_from(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
    request: AddBrickRequest,
) -> BrickRead:
    return brick_service.add_brick_from(
        session=session,
        source_brick_id=brick_id,
        island_id=request.island_id,
        learner_id=learner.id,
    )


@router.post("/{brick_id}/report", status_code=status.HTTP_201_CREATED)
def report_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
    request: BrickReportCreate = BrickReportCreate(),
) -> Response:
    brick_service.report_brick(
        session=session,
        brick_id=brick_id,
        learner_id=learner.id,
        reason=request.reason,
    )
    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/{brick_id}/forget", status_code=status.HTTP_204_NO_CONTENT)
def forget_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
) -> Response:
    brick_service.forget_brick(
        session=session,
        brick_id=brick_id,
        learner_id=learner.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{brick_id}/skip", status_code=status.HTTP_204_NO_CONTENT)
def skip_brick(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
    is_skipped: bool = True,
) -> Response:
    brick_service.skip_brick(
        session=session,
        brick_id=brick_id,
        learner_id=learner.id,
        is_skipped=is_skipped,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/add-from-island/{island_id}",
    response_model=AddIslandResult,
)
def add_bricks_from_island(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    island_id: int,
    request: AddIslandRequest,
) -> AddIslandResult:
    result = brick_service.add_bricks_from_island(
        session=session,
        source_island_id=island_id,
        target_island_id=request.target_island_id,
        learner_id=learner.id,
    )
    return AddIslandResult(**result)


@router.get("/{brick_id}", response_model=BrickDetailRead)
def get_brick_detail(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
) -> BrickDetailRead:
    return brick_service.get_brick_detail(
        session=session,
        brick_id=brick_id,
        learner_id=learner.id,
    )


@router.get("/{brick_id}/audio")
def get_brick_audio(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    brick_id: int,
) -> str:
    return audio_cache_service.get_brick_audio_url(
        session=session,
        brick_id=brick_id,
        learner_id=learner.id,
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
    target_audio_path, _ = await file_utils.save_upload_file_to_cloud(
        file=target_audio_file,
        relative_path=LEARNER_AUDIOS_DIR / f"learner-{creator_id}",
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
        target_audio_path, _ = await file_utils.save_upload_file_to_cloud(
            file=target_audio_file,
            relative_path=LEARNER_AUDIOS_DIR / f"learner-{learner.id}",
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
