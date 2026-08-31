from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class LearnerRead(SQLModel):
    id: int
    name: str


class LearnerDetailRead(SQLModel):
    id: int
    name: str
    email: EmailStr | None = None


class LearnerUpdateName(SQLModel):
    name: str = Field(min_length=1, max_length=100)
