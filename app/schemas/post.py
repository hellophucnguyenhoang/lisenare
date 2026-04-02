from sqlmodel import SQLModel
from datetime import datetime
from .learner import LearnerRead


class PostRead(SQLModel):
    id: int
    content: str
    translation: str | None = None
    audio_uri: str
    accent: str | None
    created_at: datetime
    creator: LearnerRead


class PostPage(SQLModel):
    items: list[PostRead]
    total: int
