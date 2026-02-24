from sqlmodel import SQLModel

class LearnerAccountCreate(SQLModel):
    full_name: str = "Phuc Nguyen"
    username: str = "asdf"
    password: str = "1234"
    email: str | None = None

class ChangePasswordRequest(SQLModel):
    old_password: str
    new_password: str
