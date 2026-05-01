from enum import Enum
from typing import Annotated

from sqlmodel import Field, SQLModel

from app.schemas import ReviewBase


class SentenceCompareRequest(SQLModel):
    sentence1: Annotated[str, Field(description="The learner's sentence")] = (
        "How are you?"
    )
    sentence2: Annotated[str, Field(description="The model's sentence")] = (
        "What's up?"
    )
    review_base: ReviewBase | None = None


class SentenceCompareResponse(SQLModel):
    score: float
    correct: bool | None = None
    threshold: float = 0.7


class Language(str, Enum):
    vi = "vi"
    en = "en"


class SentenceTranslateRequest(SQLModel):
    text: str = "what's up?"
    target_lang: Language = Language.vi


class SentenceTranslateResponse(SQLModel):
    text: str
    lang: Language = Language.en
