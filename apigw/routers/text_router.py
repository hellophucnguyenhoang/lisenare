from typing import Annotated

from fastapi import APIRouter, Depends, status

import http_client as http_client
from config import settings
from constants import GENERATED_AUDIOS_DIR
from database import Learner
from exceptions import RequestException
from services import auth_service
from services.text_service import text_service
from shared_constants import BRICK_AVG_WORD_LEN, BRICK_MAX_WORDS
from shared_schemas.sentence import (
    SentenceCompareRequest,
    SentenceCompareResponse,
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
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    comparison_payload: SentenceCompareRequest,
) -> SentenceCompareResponse:
    lang = comparison_payload.lang or current_learner.retrieval_lang
    comparison_payload.lang = lang

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
            lang=lang,
        ).model_dump(mode="json"),
    )
    phoneme_data = PhonemeAnalysisResponse.model_validate(
        phoneme_response.json()
    )
    teacher_phonemes = phoneme_data.teacher_phonemes
    learner_phonemes = phoneme_data.learner_phonemes
    phoneme_analysis = text_service.evaluate_phoneme_pronunciation(
        teacher_phonemes=teacher_phonemes,
        learner_phonemes=learner_phonemes,
        lang=lang,
    )

    # 3. Update evaluation if phoneme tracking yields a higher accuracy score
    phoneme_accuracy = phoneme_analysis["accuracy_score"]
    if phoneme_accuracy > evaluation_result.score:
        evaluation_result.score = phoneme_accuracy
        evaluation_result.correct = (
            phoneme_accuracy >= evaluation_result.threshold
        )

    return evaluation_result


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
        relative_path=GENERATED_AUDIOS_DIR,
        filename_prefix="tts",
    )
    return f"{settings.asset_base_url}/{relative_path}"
