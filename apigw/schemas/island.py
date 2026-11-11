from datetime import datetime

from pydantic import field_validator

from schemas.base import Schema
from utils.tag_utils import clean_tags


class IslandBase(Schema):
    name: str
    description: str | None = None


class IslandCreate(IslandBase):
    tags: list[str] = []

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags_field(cls, v: list[str] | None) -> list[str]:
        if v is None:
            return []
        return clean_tags(v)


class IslandUpdate(Schema):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags_field(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return clean_tags(v)


class IslandRead(IslandBase):
    id: int
    creator_id: int
    created_at: datetime
    brick_count: int | None = None
    learned_count: int | None = None
    tags: list[str] = []

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags_field(cls, v: list[str] | None) -> list[str]:
        if v is None:
            return []
        return clean_tags(v)


class IslandRenameRequest(Schema):
    new_name: str
