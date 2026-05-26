from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlmodel import Session

import app.http_client as http_client
from app.database import Learner, get_session
from app.schemas import (
    ReviewCreate,
)
from app.services import (
    auth_service,
    learning_card_service,
    review_service,
)
from app.services.text_service import text_service
from schemas.sentence import (
    SentenceCompareRequest,
    SentenceCompareResponse,
    SentenceTranslateRequest,
    SentenceTranslateResponse,
)
from schemas.text import WavStreamingResponse
from utils import text_utils

router = APIRouter(prefix="/text", tags=["Text Features"])


@router.post("/sentence-comparison")
async def compare_learner_pronunciation(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    background_tasks: BackgroundTasks,
    comparison_payload: SentenceCompareRequest,
) -> SentenceCompareResponse:
    # 1. Fetch external semantic evaluation
    http_response = await http_client.get_client().post(
        "/text/semantic-comparison",
        json=comparison_payload.model_dump(mode="json"),
    )
    evaluation_result = SentenceCompareResponse.model_validate(
        http_response.json()
    )

    # 2. Extract and analyze linguistic phonemes
    reference_ipa, learner_ipa, _, _ = text_utils.analyze_phoneme(
        comparison_payload.sentence2,
        comparison_payload.sentence1,
    )
    phoneme_analysis = text_service.evaluate_ipa_pronunciation(
        teacher_ipa=reference_ipa, learner_ipa=learner_ipa
    )

    # 3. Update evaluation if phoneme tracking yields a higher accuracy score
    phoneme_accuracy = phoneme_analysis["accuracy_score"]
    if phoneme_accuracy > evaluation_result.score:
        evaluation_result.score = phoneme_accuracy
        evaluation_result.correct = (
            phoneme_accuracy > evaluation_result.threshold
        )

    # 4. Handle persistence and scheduling optimization if tracking data is provided
    if comparison_payload.review_base:
        review_metadata = ReviewCreate(
            **comparison_payload.review_base.model_dump(exclude_none=True),
            first_score=evaluation_result.score,
            user_target_text=comparison_payload.sentence1,
        )
        total_saved_reviews = review_service.save_review(
            session=session,
            learner_id=current_learner.id,
            review_create=review_metadata,
        )
        print(f"Review saved, {total_saved_reviews = }")

        # Optimize spacing intervals periodically
        if total_saved_reviews > 100 and total_saved_reviews % 200 == 0:
            background_tasks.add_task(
                learning_card_service.optimize_user_scheduler,
                current_learner.id,
            )
            print(
                f"Triggering background optimization for learner {current_learner.id}"
            )

        learning_card_service.update_learning_card(
            session=session,
            learner_id=current_learner.id,
            brick_id=comparison_payload.review_base.brick_id,
            score=evaluation_result.score,
            is_answer_revealed=comparison_payload.review_base.is_answer_revealed,
        )

    return evaluation_result


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
