from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ai_model_server.services.text_service import text_service
from ai_model_server.services.readmepp_service import readmepp_service
from app.services import chat_service
from schemas.sentence import (
    SentenceCompareRequest,
    SentenceCompareResponse,
    SentenceTranslateRequest,
    SentenceTranslateResponse,
)
from schemas.cefr import (
    CEFRRequest,
    CEFRResponse,
    CEFRLevel,
)
from schemas.chat import ChatRequest


router = APIRouter(prefix="/text", tags=["Text Features"])


@router.post("/semantic-comparison", response_model=SentenceCompareResponse)
def compare(sentence_compare_req: SentenceCompareRequest):
    score = text_service.get_similarity(
        sentence_compare_req.sentence1, sentence_compare_req.sentence2
    )
    sentence_compare_res = SentenceCompareResponse(score=score)
    sentence_compare_res.correct = score >= sentence_compare_res.threshold
    return sentence_compare_res


@router.post("/translations", response_model=SentenceTranslateResponse)
def translate(sentence_translate_req: SentenceTranslateRequest):
    target_text, target_lang = text_service.translate(
        sentence_translate_req.text, sentence_translate_req.target_lang
    )
    sentence_translate_res = SentenceTranslateResponse(
        text=target_text, lang=target_lang
    )
    return sentence_translate_res


@router.post("/chat")
def chat_endpoint(request: ChatRequest):
    print(f"request:{request}")
    # Convert Pydantic models back to dictionaries for the Ollama client
    history_as_dicts = [m.model_dump() for m in request.messages]
    return StreamingResponse(
        chat_service.generate_ollama_stream(history_as_dicts),
        media_type="text/plain",
    )


@router.post("/cefr-level")
def chat_endpoint(cefr_request: CEFRRequest):
    pred = readmepp_service.predict(
        cefr_request.english_sentence, return_index=False
    )
    return CEFRResponse(cefr_level=CEFRLevel(pred))
