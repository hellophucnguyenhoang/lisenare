from sqlmodel import SQLModel
from datetime import datetime

class CollectionBase(SQLModel):
    name: str

class CollectionRead(CollectionBase):
    id: int
    creator_id: int
    created_at: datetime
    brick_count: int | None = None

class CollectionCreate(CollectionBase):
    pass