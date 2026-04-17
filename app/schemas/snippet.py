from datetime import datetime

from sqlmodel import SQLModel

from .learner import LearnerRead


class SnippetBase(SQLModel):
    content: str
    translation: str | None = None


class SnippetRead(SnippetBase):
    id: int
    audio_path: str
    created_at: datetime
    creator: LearnerRead


class SnippetPage(SQLModel):
    items: list[SnippetRead]
    total: int


class SnippetCreate(SnippetBase):
    pass
