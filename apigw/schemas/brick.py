from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import field_validator, model_validator
from sqlmodel import SQLModel

from schemas.learner import LearnerRead
from utils.tag_utils import clean_tags


class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    target_lang: str | None = None
    target_pron: str | None = None
    context: str | None = None
    kind: str | None = None
    is_private: bool | None = None
    island_id: int | None = None
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags_field(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return clean_tags(v)


class BrickContextSearch(SQLModel):
    brick_id: int
    native_text: str
    target_text: str
    is_own: bool = False


class AddBrickRequest(SQLModel):
    island_id: int


class BrickReportCreate(SQLModel):
    reason: str = "Not provided"


class AddIslandRequest(SQLModel):
    target_island_id: int


class AddIslandResult(SQLModel):
    added: int
    skipped: int


class BrickMemoryExport(SQLModel):
    fsrs_card_dict: dict = {}
    due: datetime
    created_at: datetime | None = None


class BrickReviewExport(SQLModel):
    reviewed_at: datetime
    first_score: float
    is_answer_revealed: bool = False
    fsrs_rating: int = 3
    fsrs_log_dict: dict = {}
    learner_target_text: str | None = None
    learner_target_audio_path: str | None = None


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
    memory: BrickMemoryExport | None = None
    review_history: list[BrickReviewExport] | None = None

    @model_validator(mode="before")
    @classmethod
    def check_reviews_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "review_history" not in data and "reviews" in data:
                data["review_history"] = data["reviews"]
        return data

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags_field(cls, v: list[str] | None) -> list[str]:
        if v is None:
            return []
        return clean_tags(v)


class BrickBase(SQLModel):
    native_text: str
    target_text: str
    target_lang: str = "en"
    target_pron: str | None = None
    context: str | None = None
    kind: str = "sentence"
    is_private: bool = True
    tags: list[str] = []
    island_id: int

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags_field(cls, v: list[str] | None) -> list[str]:
        if v is None:
            return []
        return clean_tags(v)


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
    island_name: str = ""


class BrickCreateRequest(BrickBase):
    pass


class BrickPage(SQLModel):
    items: list[BrickLearnRead | BrickRead]
    total: int


class BrickListeningData(SQLModel):
    audio_path: str
    target_text: str
    native_text: str
    target_pron: str | None = None
    context: str | None = None


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
