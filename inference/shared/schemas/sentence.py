from typing import Annotated

from pydantic import BaseModel, Field

from shared.constants import PASS_SCORE


class SentenceCompareRequest(BaseModel):
    sentence1: Annotated[str, Field(description="The learner's sentence")] = (
        "How are you?"
    )
    sentence2: Annotated[str, Field(description="The model's sentence")] = (
        "What's up?"
    )
    lang: str | None = Field(
        default=None, description="Language code ('en', 'ja', etc.)"
    )


class SentenceCompareResponse(BaseModel):
    score: float
    correct: bool | None = None
    threshold: float = PASS_SCORE
