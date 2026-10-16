from datetime import datetime

from sqlmodel import SQLModel


class IslandBase(SQLModel):
    name: str
    description: str | None = None


class IslandCreate(IslandBase):
    tags: list[str] = []


class IslandUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class IslandRead(IslandBase):
    id: int
    creator_id: int
    created_at: datetime
    brick_count: int | None = None
    learned_count: int | None = None
    tags: list[str] = []


class IslandRenameRequest(SQLModel):
    new_name: str
