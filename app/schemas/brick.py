from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    is_public: bool | None = None
    collection_ids: list[int] | None = None

class BrickBase(SQLModel):
    native_text: str
    target_text: str
    target_audio_uri: str
    is_public: bool = True
    creator_id: int

class BrickRead(BrickBase):
    id: int
    last_edit_at: datetime

class BrickCreate(BrickBase):
    pass
