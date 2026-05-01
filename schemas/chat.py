from enum import Enum

from sqlmodel import SQLModel


class ChatRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Message(SQLModel):
    role: ChatRole = ChatRole.user
    content: str = "Answer in one sentence, why is the sky blue?"


class ChatRequest(SQLModel):
    messages: list[Message]


class ChatLearnerRequest(SQLModel):
    learner_question: str
