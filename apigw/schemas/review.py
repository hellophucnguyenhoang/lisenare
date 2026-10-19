from datetime import datetime, timezone
from typing import Any

from fsrs import Rating
from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel


class ReviewBase(SQLModel):
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    brick_id: int
    is_answer_revealed: bool = False
    learner_target_text: str | None = None
    learner_target_audio_path: str | None = None


class ReviewCreate(ReviewBase):
    rating: Rating = Field(
        description="FSRS Rating: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy)",
    )
    first_score: float = 0.0

    @field_validator("rating", mode="before")
    @classmethod
    def parse_rating(cls, v: Any) -> Any:
        if isinstance(v, str):
            mapping = {
                "again": Rating.Again,
                "hard": Rating.Hard,
                "good": Rating.Good,
                "easy": Rating.Easy,
            }
            if v.lower() in mapping:
                return mapping[v.lower()]
        return v

    @model_validator(mode="before")
    @classmethod
    def check_rating(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rating" not in data and "fsrs_rating" in data:
                data["rating"] = data["fsrs_rating"]
        return data

    @field_validator("first_score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(v, 4)


class ReviewResponse(SQLModel):
    total_reviews: int
