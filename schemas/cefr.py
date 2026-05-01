from enum import Enum

from sqlmodel import SQLModel


class CEFRLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


CEFR_MAPPING = {
    "A1": "Vỡ lòng",
    "A2": "Sơ cấp",
    "B1": "Trung cấp",
    "B2": "Cao trung cấp",
    "C1": "Cao cấp",
    "C2": "Thành thạo",
}


class CEFRRequest(SQLModel):
    english_sentence: str


class CEFRResponse(SQLModel):
    cefr_level: CEFRLevel
