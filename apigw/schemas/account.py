from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class LearnerAccountCreate(SQLModel):
    name: str = "The Avid Learner"
    username: str = Field(default="qwerwert", min_length=3)
    password: str = Field(default="kcmtl5cM#", min_length=8)
    email: EmailStr | None = Field(default=None)


class PasswordChangeRequest(SQLModel):
    old_password: str
    new_password: str


class PasswordResetRequest(SQLModel):
    username: str
    new_password: str = Field(min_length=8)
    otp: str


class SendOTPRequest(SQLModel):
    username: str


class EmailChangeOTPRequest(SQLModel):
    old_email: EmailStr | None = None
    new_email: EmailStr


class EmailChangeRequest(SQLModel):
    old_email: EmailStr | None = None
    new_email: EmailStr
    otp: str
