from sqlmodel import Field, SQLModel


class ExplanationRequest(SQLModel):
    target_term: str


class ExplanationResponse(SQLModel):
    target_term: str = Field(
        description="The word, phrase, or sentence the learner wants to understand.",
    )

    explanation: str = Field(
        description="One short explanation sentence.",
    )

    examples: list[str] = Field(
        default_factory=list,
        description="Example sentences containing the target text.",
    )

    familiarity_before: float | None = None
    familiarity_after: float | None = None
    familiarity_improvement: float | None = None
    response_time_ms: float | None = None
