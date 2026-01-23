from sqlmodel import SQLModel
from datetime import datetime
from .cefr import CEFRLevel

class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    cefr_level: CEFRLevel | None = None
    is_public: bool | None = None
    collection_ids: list[int] | None = None

class BrickBase(SQLModel):
    native_text: str
    target_text: str
    target_audio_uri: str
    cefr_level: CEFRLevel
    is_public: bool = True
    creator_id: int

class BrickRead(BrickBase):
    id: int
    last_edit_at: datetime

class BrickCreate(BrickBase):
    pass
