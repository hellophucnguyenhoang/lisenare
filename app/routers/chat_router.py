from collections.abc import Iterable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services import chat_service
from schemas.chat import ChatLearnerRequest

router = APIRouter(prefix="/chat", tags=["Chat Features"])


@router.post("", response_class=StreamingResponse)
def chat_endpoint(
    request: ChatLearnerRequest,
) -> Iterable[str]:
    for chunk_text in chat_service.generate_response_stream(
        request.learner_question
    ):
        yield chunk_text
