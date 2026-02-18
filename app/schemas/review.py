from datetime import datetime
from sqlmodel import SQLModel
from pydantic import field_validator

class ReviewBase(SQLModel):
    brick_id: int
    reviewed_at: datetime
    is_answer_revealed: bool = False

class ReviewCreate(ReviewBase):
    first_score: float
    @field_validator('first_score')
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(v, 4)

