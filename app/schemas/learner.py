from sqlmodel import SQLModel


class LearnerRead(SQLModel):
    id: int
    full_name: str
