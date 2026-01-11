from sqlmodel import SQLModel
from enum import Enum
from datetime import datetime

class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(SQLModel):
    sub: str # learner_id, store as string for required
    username: str
    exp: int
    
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

class CollectionRead(SQLModel):
    id: int
    name: str
    creator_id: int
    created_at: datetime
    brick_count: int | None = None

class LearnerAccountCreate(SQLModel):
    full_name: str
    username: str
    password: str
    email: str | None = None

class SentenceCompareRequest(SQLModel):
    sentence1: str
    sentence2: str

class SentenceCompareResponse(SQLModel):
    score: float
    correct: bool | None = None
    threshold: float = 0.7

class Language(str, Enum):
    vi = "vi"
    en = "en"

class SentenceTranslateRequest(SQLModel):
    text: str
    target_lang: Language = Language.vi

class SentenceTranslateResponse(SQLModel):
    text: str
    lang: Language = Language.en

class CollectionCreate(SQLModel):
    name: str
