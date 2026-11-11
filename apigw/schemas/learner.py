from pydantic import EmailStr, Field

from constants import MAX_PATH_LEN
from schemas.base import Schema


class LearnerRead(Schema):
    id: int
    name: str
    retrieval_lang: str = "en"
    avatar_path: str | None = None


class LearnerDetailRead(Schema):
    id: int
    name: str
    email: EmailStr | None = None
    retrieval_lang: str = "en"
    avatar_path: str | None = None


class LearnerUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    retrieval_lang: str | None = Field(
        default=None, min_length=2, max_length=2
    )
    avatar_path: str | None = Field(default=None, max_length=MAX_PATH_LEN)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "jack",
                "retrieval_lang": "en",
                "avatar_path": "default-images/meo.webp",
            }
        }
    }
