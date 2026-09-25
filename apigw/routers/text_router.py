from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlmodel import Session

import http_client as http_client
from config import settings
from database import Learner, get_session
from exceptions import RequestException
from schemas import (
    ReviewCreate,
)
from services import (
    auth_service,
    brick_memory_service,
    brick_review_service,
)
from services.text_service import text_service
from shared_constants import BRICK_AVG_WORD_LEN, BRICK_MAX_WORDS
from shared_schemas.sentence import (
    SentenceCompareRequest,
    SentenceCompareResponse,
    SentenceTranslateRequest,
    SentenceTranslateResponse,
)
from shared_schemas.text import (
    PhonemeAnalysisRequest,
    PhonemeAnalysisResponse,
    TTSRequest,
)
from utils import file_utils

router = APIRouter(prefix="/text", tags=["Text Features"])


@router.post("/sentence-comparison")
def compare_sentences(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    background_tasks: BackgroundTasks,
    comparison_payload: SentenceCompareRequest,
) -> SentenceCompareResponse:
    # 1. Fetch external semantic evaluation
    http_response = http_client.get_client().post(
        "/text/semantic-comparison",
        json=comparison_payload.model_dump(mode="json"),
    )
    evaluation_result = SentenceCompareResponse.model_validate(
        http_response.json()
    )

    # 2. Extract and analyze linguistic phonemes
    phoneme_response = http_client.get_client().post(
        "/text/phoneme-analysis",
        json=PhonemeAnalysisRequest(
            target_text=comparison_payload.sentence2,
            learner_text=comparison_payload.sentence1,
        ).model_dump(mode="json"),
    )
    phoneme_data = PhonemeAnalysisResponse.model_validate(
        phoneme_response.json()
    )
    reference_ipa = phoneme_data.teacher_ipa
    learner_ipa = phoneme_data.learner_ipa
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
        )
        total_learner_reviews = brick_review_service.save_review(
            session=session,
            learner_id=current_learner.id,
            review_create=review_metadata,
        )
        print(f"Review saved, {total_learner_reviews=}")

        # Optimize spacing intervals periodically
        if total_learner_reviews > 100:
            interval = max(200, int(total_learner_reviews**0.5 * 20))
            if total_learner_reviews % interval == 0:
                background_tasks.add_task(
                    brick_memory_service.optimize_learner_scheduler,
                    current_learner.id,
                )
                print(
                    f"Triggering background optimization for learner {current_learner.id}"
                )

    return evaluation_result


@router.post("/translations")
def translate(
    sentence_translate_request: SentenceTranslateRequest,
) -> SentenceTranslateResponse:
    r = http_client.get_client().post(
        "/text/translations",
        json=sentence_translate_request.model_dump(mode="json"),
    )
    sentence_translate_respond = SentenceTranslateResponse.model_validate(
        r.json()
    )
    return sentence_translate_respond


@router.post(
    "/to-speech",
    description="Convert text to speech, save audio locally, and return relative path.",
)
def text_to_speech(
    tts_request: TTSRequest,
) -> str:
    max_chars = BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN
    if len(tts_request.text) > max_chars:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Text exceeds maximum length of {max_chars} characters",
        )

    response = http_client.get_client().post(
        "/text/to-speech",
        json=tts_request.model_dump(mode="json"),
    )
    if response.status_code != status.HTTP_200_OK:
        raise RequestException(
            status_code=response.status_code,
            debug_message=f"Inference server error: {response.text}",
        )

    relative_path = file_utils.save_file_bytes(
        content=response.content,
        base_dir=settings.generated_audios_folder,
        filename_prefix="tts",
        extension=".wav",
    )
    return relative_path
