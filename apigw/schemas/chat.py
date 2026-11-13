from enum import Enum

from schemas.base import Schema


class ChatRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class ChatMessage(Schema):
    role: ChatRole = ChatRole.user
    content: str = "Answer in one sentence, why is the sky blue?"


class ChatRequest(Schema):
    messages: list[ChatMessage]


class ChatLearnerRequest(Schema):
    chat_session_id: str
    learner_question: str
