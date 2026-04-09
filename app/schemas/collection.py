from datetime import datetime
from enum import Enum

from sqlmodel import SQLModel


class CollectionBase(SQLModel):
    name: str
    group_name: str = "my group"


class CollectionRead(CollectionBase):
    id: int
    creator_id: int
    created_at: datetime
    brick_count: int | None = None
    learned_count: int | None = None


class GroupStats(SQLModel):
    group_name: str
    collection_count: int


class CollectionStatus(str, Enum):
    ALL = "all"
    NOT_STARTED = "not_started"  # chưa học
    IN_PROGRESS = "in_progress"  # đang học
    COMPLETED = "completed"  # hoàn thành


class CollectionSort(str, Enum):
    recommended = "recommended"
    newest = "newest"
    az = "az"
    za = "za"
