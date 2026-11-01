from pydantic import EmailStr
from sqlmodel import Field, SQLModel

from constants import MAX_PATH_LEN


class LearnerRead(SQLModel):
    id: int
    name: str
    retrieval_lang: str = "en"
    avatar_path: str | None = None


class LearnerDetailRead(SQLModel):
    id: int
    name: str
    email: EmailStr | None = None
    retrieval_lang: str = "en"
    avatar_path: str | None = None


class LearnerUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    retrieval_lang: str | None = Field(
        default=None, min_length=2, max_length=2
    )
    avatar_path: str | None = Field(default=None, max_length=MAX_PATH_LEN)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "jack",
                "retrieval_lang": "en",
                "avatar_path": "default-images/meo.webp",
            }
        }
