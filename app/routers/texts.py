from app.services.text_service import text_service
from fastapi import APIRouter
from app.schemas import (SentenceCompareRequest, 
                         SentenceCompareResponse, 
                         SentenceTranslateRequest, 
                         SentenceTranslateResponse)

router = APIRouter(prefix="/text", tags=["Text Features"])

@router.post("/comparisons", response_model=SentenceCompareResponse)
async def compare(sentence_compare_req: SentenceCompareRequest):
    score = text_service.get_similarity(sentence_compare_req.sentence1, sentence_compare_req.sentence2)
    sentence_compare_res = SentenceCompareResponse(score=score)
    sentence_compare_res.correct = score >= sentence_compare_res.threshold
    return sentence_compare_res

@router.post("/translations", response_model=SentenceTranslateResponse)
async def translate(sentence_translate_req: SentenceTranslateRequest):
    target_text, target_lang = text_service.translate(sentence_translate_req.text, sentence_translate_req.target_lang)
    sentence_translate_res = SentenceTranslateResponse(
        text=target_text,
        lang=target_lang
    )
    return sentence_translate_res
