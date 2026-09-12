from fastapi import APIRouter, HTTPException, Response, status

from app.config import settings
from inference.services.text_service import text_service
from schemas.sentence import (
    SentenceCompareRequest,
    SentenceCompareResponse,
    SentenceTranslateRequest,
    SentenceTranslateResponse,
)
from schemas.text import TTSRequest

router = APIRouter(prefix="/text", tags=["Text Features"])


@router.post("/semantic-comparison")
def compare(
    sentence_compare_req: SentenceCompareRequest,
) -> SentenceCompareResponse:
    score = text_service.get_similarity(
        sentence_compare_req.sentence1, sentence_compare_req.sentence2
    )
    sentence_compare_res = SentenceCompareResponse(score=score)
    sentence_compare_res.correct = score >= sentence_compare_res.threshold
    return sentence_compare_res


@router.post("/translations")
def translate(
    sentence_translate_req: SentenceTranslateRequest,
) -> SentenceTranslateResponse:
    target_text, target_lang = text_service.translate(
        sentence_translate_req.text, sentence_translate_req.target_lang
    )
    sentence_translate_res = SentenceTranslateResponse(
        text=target_text, lang=target_lang
    )
    return sentence_translate_res


@router.post("/to-speech")
def generate_tts_audio(
    tts_request: TTSRequest,
) -> Response:
    max_chars = settings.brick_max_words * settings.brick_avg_word_len
    if len(tts_request.text) > max_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Text exceeds maximum length of {max_chars} characters",
        )

    audio_bytes = text_service.generate_tts_wav(
        text=tts_request.text,
        voice=tts_request.voice,
    )
    return Response(content=audio_bytes, media_type="audio/wav")
