from datetime import datetime

from sqlmodel import SQLModel

from .learner import LearnerRead


class SnippetRead(SQLModel):
    id: int
    content: str
    audio_path: str
    created_at: datetime
    translation: str | None = None
    creator: LearnerRead


class SnippetPage(SQLModel):
    items: list[SnippetRead]
    total: int
