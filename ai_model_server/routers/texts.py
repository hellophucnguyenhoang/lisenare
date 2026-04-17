from fastapi import APIRouter

from ai_model_server.services.readmepp_service import readmepp_service
from ai_model_server.services.text_service import text_service
from schemas.cefr import (
    CEFRRequest,
    CEFRResponse,
)
from schemas.sentence import (
    SentenceCompareRequest,
    SentenceCompareResponse,
    SentenceTranslateRequest,
    SentenceTranslateResponse,
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


@router.post("/cefr-level")
def predict_cefr(cefr_request: CEFRRequest) -> CEFRResponse:
    pred = readmepp_service.predict(
        cefr_request.english_sentence, return_index=False
    )
    return CEFRResponse(cefr_level=pred)
