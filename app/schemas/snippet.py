from datetime import datetime

from sqlmodel import SQLModel

from .learner import LearnerRead


class SnippetBase(SQLModel):
    content: str
    translation: str | None = None


class SnippetCreate(SnippetBase):
    pass


class SnippetRead(SnippetBase):
    id: int
    audio_path: str
    created_at: datetime
    creator: LearnerRead
    is_liked: bool = False


class SnippetPage(SQLModel):
    items: list[SnippetRead]
    total: int
