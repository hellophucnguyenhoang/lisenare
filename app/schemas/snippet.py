from datetime import datetime

from sqlmodel import SQLModel

from .learner import LearnerRead


class SnippetBase(SQLModel):
    id: int
    content: str
    translation: str | None = None
    content_audio_path: str | None = None
    content_pron: str | None = None
    context: str | None = None
    is_public: bool = True
    last_edit_at: datetime
    creator: LearnerRead
    reaction: str | None = None  # LIKE / DISLIKE / None


class SnippetRead(SnippetBase):
    contribution_count: int
    tags: list[str] = []


class SnippetPage(SQLModel):
    items: list[SnippetRead]
    total: int
