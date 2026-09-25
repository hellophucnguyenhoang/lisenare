from datetime import datetime, timezone

from pydantic import field_validator
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
    first_score: float

    @field_validator("first_score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(v, 4)
