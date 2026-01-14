from sqlmodel import SQLModel
from enum import Enum

class ChatRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"

class Message(SQLModel):
    role: ChatRole = ChatRole.user
    content: str

class ChatRequest(SQLModel):
    messages: list[Message]
