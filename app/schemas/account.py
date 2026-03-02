from sqlmodel import SQLModel, Field


class LearnerAccountCreate(SQLModel):
    full_name: str = "Phuc Nguyen"
    username: str = "asdf"
    password: str = Field(default="12345678", min_length=8)
    email: str | None = None


class PasswordChangeRequest(SQLModel):
    old_password: str
    new_password: str


class PasswordResetRequest(SQLModel):
    username: str
    new_password: str = Field(min_length=8)
    otp: str
