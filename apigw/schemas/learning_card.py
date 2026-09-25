from datetime import date, datetime

from sqlmodel import Field, SQLModel


class LearningCardStats(SQLModel):
    total_learning: int = Field(ge=0)
    due_count: int = Field(ge=0)
    true_retention: float = Field(ge=0.0, le=1.0)
    average_stability: float = Field(ge=0.0)  # in days
    total_memorized: float = Field(ge=0.0)
    timestamp: datetime


class TimeSeriesPoint(SQLModel):
    date: date  # "2026-04-01"
    value: float


class LearningTimeSeries(SQLModel):
    metric: str  # e.g. "total_learning"
    unit: str  # e.g. "cards"
    data: list[TimeSeriesPoint]
