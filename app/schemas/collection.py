from sqlmodel import SQLModel
from datetime import datetime


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
