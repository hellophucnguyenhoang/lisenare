from typing import Literal

from sqlmodel import Field, SQLModel


class ContextSearchRequest(SQLModel):
    query: str = "hang out"
    kind: Literal["word", "sentence"] | None = None
    limit: int = Field(default=30, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
