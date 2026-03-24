from sqlmodel import SQLModel, Field


class TextFrequencyRequest(SQLModel):
    english_sentence: str = "I ate breakfast at home."


class TextFrequencyResponse(SQLModel):
    frequency: float = Field(ge=0, le=1)
