from typing import Annotated

from sqlmodel import Field, SQLModel


class SentenceCompareRequest(SQLModel):
    sentence1: Annotated[str, Field(description="The learner's sentence")] = (
        "How are you?"
    )
    sentence2: Annotated[str, Field(description="The model's sentence")] = (
        "What's up?"
    )
    lang: str | None = Field(
        default=None, description="Language code ('en', 'ja', etc.)"
    )


class SentenceCompareResponse(SQLModel):
    score: float
    correct: bool | None = None
    threshold: float = 0.7
