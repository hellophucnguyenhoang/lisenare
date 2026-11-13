from collections.abc import Iterable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from schemas.chat import ChatLearnerRequest, ChatMessage
from services import chat_service

router = APIRouter(prefix="/chat", tags=["Chat Features"])


@router.post("", response_class=StreamingResponse)
def chat_endpoint(request: ChatLearnerRequest) -> Iterable[str]:
    for chunk_text in chat_service.generate_chat_stream(
        request.chat_session_id,
        request.learner_question,
    ):
        yield chunk_text


@router.get("/{session_id}", response_model=list[ChatMessage])
def get_chat_messages(session_id: str) -> list[ChatMessage]:
    return chat_service.get_chat_messages(session_id)
