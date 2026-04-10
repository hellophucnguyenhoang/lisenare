from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session
from wordfreq import word_frequency

import app.http_client as http_client
from app.database import Learner, get_session
from app.schemas import (
    ReviewCreate,
    TextFrequencyRequest,
    TextFrequencyResponse,
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

router = APIRouter(prefix="/text", tags=["Text Features"])


@router.get(
    "/forced_alignment/{audio_path:path}",
    response_model=list[WordSegmentSecond],
)
def forced_align(audio_path: str):
    return forced_alignment_service.align(audio_path)


@router.post("/semantic-comparison", response_model=SentenceCompareResponse)
async def compare(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    sentence_compare_request: SentenceCompareRequest,
):
    r = await http_client.client.post(
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
            learner_id=current_learner.id,
            review_create=review_create,
        )
        learning_card_service.update_learning_card(
            session=session,
            learner_id=current_learner.id,
            brick_id=sentence_compare_request.review_base.brick_id,
            score=sentence_compare_response.score,
            is_answer_revealed=sentence_compare_request.review_base.is_answer_revealed,
        )
    return sentence_compare_response


@router.post("/translations", response_model=SentenceTranslateResponse)
async def translate(
    sentence_translate_request: SentenceTranslateRequest,
):
    r = await http_client.client.post(
        "/text/translations",
        json=sentence_translate_request.model_dump(mode="json"),
    )
    sentence_translate_respond = SentenceTranslateResponse.model_validate(
        r.json()
    )
    return sentence_translate_respond


@router.post("/frequency")
def get_text_frequency(text_frequency_request: TextFrequencyRequest):
    # Tokenize the sentence and get the frequency of every token,
    # then aggregate them using the Harmonic Mean
    # Formula: 1 / (1/f1 + 1/f2 + ...)
    frequency = word_frequency(
        text_frequency_request.english_sentence, lang="en"
    )
    return TextFrequencyResponse(frequency=frequency)
