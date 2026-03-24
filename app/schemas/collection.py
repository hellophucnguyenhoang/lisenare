from sqlmodel import SQLModel
from datetime import datetime


class CollectionBase(SQLModel):
    name: str
    group_name: str = "custom"


class CollectionRead(CollectionBase):
    id: int
    creator_id: int
    created_at: datetime
    brick_count: int | None = None
    learned_count: int | None = None


class CollectionCreate(CollectionBase):
    pass


class GroupStats(SQLModel):
    group_name: str
    collection_count: int
