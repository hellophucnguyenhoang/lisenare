from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

import app.http_client as http_client
from app.database import Learner, get_session
from app.schemas import (
    ReviewCreate,
    WordSegmentSecond,
)
from app.services import (
    auth_service,
    forced_alignment_service,
    learning_card_service,
    review_service,
)
from schemas.sentence import (
    SentenceCompareRequest,
    SentenceCompareResponse,
    SentenceTranslateRequest,
    SentenceTranslateResponse,
)
from schemas.text import WavStreamingResponse

router = APIRouter(prefix="/text", tags=["Text Features"])


@router.get("/forced_alignment/{audio_path:path}")
def forced_align(
    session: Annotated[Session, Depends(get_session)], audio_path: str
) -> list[WordSegmentSecond]:
    return forced_alignment_service.align(session, audio_path)


@router.post("/semantic-comparison")
async def compare(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    sentence_compare_request: SentenceCompareRequest,
) -> SentenceCompareResponse:
    r = await http_client.get_client().post(
        "/text/semantic-comparison",
        json=sentence_compare_request.model_dump(mode="json"),
    )
    sentence_compare_response = SentenceCompareResponse.model_validate(
        r.json()
    )
    if sentence_compare_request.review_base:
        review_create = ReviewCreate(
            **sentence_compare_request.review_base.model_dump(
                exclude_none=True
            ),
            first_score=sentence_compare_response.score,
            user_target_text=sentence_compare_request.sentence1,
            # Haven't store user's audio yet for simplicity
        )
        review_service.save_review(
            session=session,
            learner_id=learner.id,
            review_create=review_create,
        )
        learning_card_service.update_learning_card(
            session=session,
            learner_id=learner.id,
            brick_id=sentence_compare_request.review_base.brick_id,
            score=sentence_compare_response.score,
            is_answer_revealed=sentence_compare_request.review_base.is_answer_revealed,
        )
    return sentence_compare_response


@router.post("/translations")
async def translate(
    sentence_translate_request: SentenceTranslateRequest,
) -> SentenceTranslateResponse:
    r = await http_client.get_client().post(
        "/text/translations",
        json=sentence_translate_request.model_dump(mode="json"),
    )
    sentence_translate_respond = SentenceTranslateResponse.model_validate(
        r.json()
    )
    return sentence_translate_respond


@router.get(
    "/tts-stream",
    response_class=WavStreamingResponse,
    description="Only works for SHORT TEXT only.",
)
async def proxy_tts_stream(
    data: str = Query(description="Base64 encoded JSON string"),
):
    # Update to a POST + GET for longer text
    async with http_client.get_client().stream(
        "GET", "/text/tts-stream", params={"data": data}
    ) as r:
        async for chunk in r.aiter_bytes():
            yield chunk
