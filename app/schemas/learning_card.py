from datetime import datetime

from sqlmodel import Field, SQLModel


class LearningCardStats(SQLModel):
    total_learning: int = Field(ge=0)
    due_count: int = Field(ge=0)
    timestamp: datetime
