from sqlmodel import SQLModel
from enum import Enum
from app.schemas import ReviewBase


class SentenceCompareRequest(SQLModel):
    sentence1: str = "How are you?"
    sentence2: str = "What's up?"
    review_base: ReviewBase | None = None


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
