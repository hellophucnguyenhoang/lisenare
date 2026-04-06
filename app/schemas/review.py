from datetime import datetime, timezone

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class ReviewBase(SQLModel):
    brick_id: int
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_answer_revealed: bool = False
    user_target_text: str | None = None
    user_target_audio_uri: str | None = None


class ReviewCreate(ReviewBase):
    first_score: float

    @field_validator("first_score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(v, 4)
