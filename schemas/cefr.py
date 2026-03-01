from sqlmodel import SQLModel
from enum import Enum


class CEFRLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class CEFRRequest(SQLModel):
    english_sentence: str


class CEFRResponse(SQLModel):
    cefr_level: CEFRLevel
