from enum import Enum

from sqlmodel import SQLModel


class ChatRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Message(SQLModel):
    role: ChatRole = ChatRole.user
    content: str = "Why is the sky blue?"


class ChatRequest(SQLModel):
    messages: list[Message]
