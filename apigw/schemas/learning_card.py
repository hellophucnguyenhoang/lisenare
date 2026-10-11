from datetime import date, datetime

from sqlmodel import Field, SQLModel


class LearningCardStats(SQLModel):
    total_learning: int = Field(ge=0)
    estimated_recalled: float = Field(ge=0.0)
    due_count: int = Field(ge=0)
    true_retention: float = Field(ge=0.0, le=1.0)
    next_due_in_seconds: int | None = Field(default=None, ge=0)
    timestamp: datetime


class TimeSeriesPoint(SQLModel):
    date: date  # "2026-04-01"
    value: float


class LearningTimeSeries(SQLModel):
    metric: str  # e.g. "total_learning"
    unit: str  # e.g. "cards"
    data: list[TimeSeriesPoint]
