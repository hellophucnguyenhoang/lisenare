from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AgentChatRequest(BaseModel):
    learner_id: int
    messages: list[AgentMessage] = Field(min_length=1)


class AgentToolCallLog(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result_summary: str


class AgentChatResponse(BaseModel):
    answer: str
    tool_calls: list[AgentToolCallLog] = Field(default_factory=list)
