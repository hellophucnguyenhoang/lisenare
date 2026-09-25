from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class LearnerRead(SQLModel):
    id: int
    name: str
    practice_lang: str = "en"


class LearnerDetailRead(SQLModel):
    id: int
    name: str
    email: EmailStr | None = None
    practice_lang: str = "en"


class LearnerUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    practice_lang: str | None = Field(default=None, min_length=2, max_length=2)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "jack",
                "practice_lang": "en",
            }
        }
