from sqlmodel import SQLModel
from datetime import datetime

class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    is_public: bool | None = None
    collection_ids: list[int] | None = None

class BrickRead(SQLModel):
    id: int
    native_text: str
    target_text: str
    target_audio_url: str
    is_public: bool = True
    last_edit_at: datetime
    creator_id: int
