from typing import Any

from pydantic import BaseModel, Field


class FSRSOptimizeRequest(BaseModel):
    review_logs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of serialized FSRS review log dicts",
    )


class FSRSOptimizeResponse(BaseModel):
    optimal_params: list[float] = Field(
        description="Optimized FSRS parameter weights",
    )
    optimal_retention: float = Field(
        default=0.9,
        description="Optimized target retention",
    )
