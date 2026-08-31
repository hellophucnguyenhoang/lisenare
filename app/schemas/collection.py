from datetime import datetime

from sqlmodel import SQLModel


class CollectionBase(SQLModel):
    name: str
    description: str | None = None


class CollectionRead(CollectionBase):
    id: int
    creator_id: int
    created_at: datetime
    brick_count: int | None = None
    learned_count: int | None = None
    tags: list[str] = []


class CollectionRenameRequest(SQLModel):
    new_name: str
