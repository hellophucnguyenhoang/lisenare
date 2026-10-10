from datetime import datetime
from enum import Enum

from sqlmodel import SQLModel

from schemas.learner import LearnerRead


class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    target_lang: str | None = None
    target_pron: str | None = None
    context: str | None = None
    kind: str | None = None
    is_private: bool | None = None
    collection_id: int | None = None
    tags: list[str] | None = None


class BrickContextSearch(SQLModel):
    brick_id: int
    native_text: str
    target_text: str
    is_own: bool = False


class AddBrickRequest(SQLModel):
    collection_id: int


class AddCollectionRequest(SQLModel):
    target_collection_id: int


class AddCollectionResult(SQLModel):
    added: int
    skipped: int


class BrickExport(SQLModel):
    native_text: str
    target_text: str
    target_audio_path: str
    target_lang: str = "en"
    target_pron: str | None = None
    context: str | None = None
    kind: str = "sentence"
    tags: list[str] = []
    is_private: bool = True


class BrickBase(SQLModel):
    native_text: str
    target_text: str
    target_lang: str = "en"
    target_pron: str | None = None
    context: str | None = None
    kind: str = "sentence"
    is_private: bool = True
    tags: list[str] = []
    collection_id: int


class BrickCreate(BrickBase):
    target_audio_path: str
    creator_id: int


class BrickRead(BrickBase):
    id: int
    target_audio_path: str
    last_edit_at: datetime
    creator_id: int
    creator: LearnerRead
    reaction: str | None = None


class BrickLearnRead(BrickRead):
    learned: bool


class BrickDetailRead(BrickRead):
    collection_name: str = ""


class BrickCreateRequest(BrickBase):
    pass


class BrickPage(SQLModel):
    items: list[BrickLearnRead | BrickRead]
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
