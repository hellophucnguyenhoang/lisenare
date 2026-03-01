from sqlmodel import SQLModel, Field
from datetime import datetime


class LearningCardStats(SQLModel):
    total_learning: int = Field(ge=0)
    due_count: int = Field(ge=0)
    timestamp: datetime
