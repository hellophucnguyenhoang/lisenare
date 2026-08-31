from datetime import datetime
from enum import Enum

from sqlmodel import SQLModel

from app.schemas.learner import LearnerRead


class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    target_pron: str | None = None
    context: str | None = None
    unit_type: str | None = None
    is_private: bool | None = None
    collection_id: int | None = None


class BrickContextSearch(SQLModel):
    brick_id: int
    native_text: str
    target_text: str


class BrickBase(SQLModel):
    native_text: str
    target_text: str
    target_pron: str | None = None
    context: str | None = None
    unit_type: str
    is_private: bool = True


class BrickCreate(BrickBase):
    target_audio_path: str
    creator_id: int
    collection_id: int
    tags: list[str] = []


class BrickRead(BrickBase):
    id: int
    target_audio_path: str
    last_edit_at: datetime
    creator_id: int
    creator: LearnerRead
    collection_id: int
    tags: list[str] = []


class BrickLearnRead(BrickRead):
    learned: bool


class BrickCreateRequest(BrickBase):
    collection_name: str


class BrickPage(SQLModel):
    items: list[BrickLearnRead]
    total: int


class BrickListeningData(SQLModel):
    audio_path: str
    target_text: str
    native_text: str


class BrickListeningPage(SQLModel):
    items: list[BrickListeningData]
    offset: int
    limit: int
    total: int


class BrickStatus(str, Enum):
    LEARNED = "LEARNED"
    NOT_LEARNED = "NOT_LEARNED"


class BrickSort(str, Enum):
    NEWEST = "NEWEST"
    AZ = "AZ"
    ZA = "ZA"
