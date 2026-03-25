from sqlmodel import SQLModel
from enum import Enum


class CEFRLevel(str, Enum):
    A1 = "Vỡ lòng (A1)"
    A2 = "Sơ cấp (A2)"
    B1 = "Trung cấp (B1)"
    B2 = "Cao trung cấp (B2)"
    C1 = "Cao cấp (C1)"
    C2 = "Thành thạo (C2)"


class CEFRRequest(SQLModel):
    english_sentence: str


class CEFRResponse(SQLModel):
    cefr_level: CEFRLevel
