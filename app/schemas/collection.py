from datetime import datetime

from sqlmodel import SQLModel


class CollectionBase(SQLModel):
    name: str


class CollectionRead(CollectionBase):
    id: int
    creator_id: int
    created_at: datetime
    brick_count: int | None = None
    learned_count: int | None = None


class CollectionRenameRequest(SQLModel):
    name: str
