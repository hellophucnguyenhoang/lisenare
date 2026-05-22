from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class LearnerRead(SQLModel):
    id: int
    full_name: str
    email: EmailStr | None


class LearnerUpdateName(SQLModel):
    full_name: str = Field(min_length=1, max_length=100)
