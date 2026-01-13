from sqlmodel import SQLModel

class LearnerAccountCreate(SQLModel):
    full_name: str
    username: str
    password: str
    email: str | None = None
