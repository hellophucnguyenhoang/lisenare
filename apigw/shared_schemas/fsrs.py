from typing import Any
from sqlmodel import Field, SQLModel


class FSRSOptimizeRequest(SQLModel):
    review_logs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of serialized FSRS review log dicts",
    )


class FSRSOptimizeResponse(SQLModel):
    optimal_params: list[float] = Field(
        description="Optimized FSRS parameter weights",
    )
    optimal_retention: float = Field(
        default=0.9,
        description="Optimized target retention",
    )
