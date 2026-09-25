from fastapi import APIRouter, HTTPException, Response, status

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
    SpellFixRequest,
    SpellFixResponse,
    StemmingRequest,
    StemmingResponse,
    TermNormalizeRequest,
    TermNormalizeResponse,
    TTSRequest,
    WordValidationRequest,
    WordValidationResponse,
)

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
    max_chars = BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN
    if len(tts_request.text) > max_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Text exceeds maximum length of {max_chars} characters",
        )
    audio_bytes = text_service.generate_tts_wav(
        text=tts_request.text,
        voice=tts_request.voice,
    )
    return Response(content=audio_bytes, media_type="audio/wav")


@router.post("/phoneme-analysis", response_model=PhonemeAnalysisResponse)
def analyze_phoneme(
    request: PhonemeAnalysisRequest,
) -> PhonemeAnalysisResponse:
    return text_service.analyze_phoneme(
        target_text=request.target_text,
        learner_text=request.learner_text,
    )


@router.post("/spell-fix", response_model=SpellFixResponse)
def spell_fix(request: SpellFixRequest) -> SpellFixResponse:
    corrected = text_service.refined_spell_fix(request.text)
    return SpellFixResponse(corrected_text=corrected)


@router.post("/normalize-term", response_model=TermNormalizeResponse)
def normalize_term(request: TermNormalizeRequest) -> TermNormalizeResponse:
    normalized_term, is_valid = text_service.normalize_target_term(
        request.term
    )
    return TermNormalizeResponse(
        normalized_term=normalized_term,
        is_valid=is_valid,
    )


@router.post("/validate-word", response_model=WordValidationResponse)
def validate_word(request: WordValidationRequest) -> WordValidationResponse:
    is_valid = text_service.is_valid_english(request.word)
    return WordValidationResponse(is_valid=is_valid)


@router.post("/stemming", response_model=StemmingResponse)
def get_stems(request: StemmingRequest) -> StemmingResponse:
    stems = text_service.get_lenient_stems(request.text)
    return StemmingResponse(stems=stems)
