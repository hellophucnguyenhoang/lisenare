from pydantic import EmailStr, Field

from schemas.base import Schema


class LearnerAccountCreate(Schema):
    name: str = "The Avid Learner"
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)
    email: EmailStr | None = Field(default=None)


class PasswordChangeRequest(Schema):
    old_password: str
    new_password: str


class PasswordResetRequest(Schema):
    username: str
    new_password: str = Field(min_length=8)
    otp: str


class SendOTPRequest(Schema):
    username: str


class EmailChangeOTPRequest(Schema):
    old_email: EmailStr | None = None
    new_email: EmailStr


class EmailChangeRequest(Schema):
    old_email: EmailStr | None = None
    new_email: EmailStr
    otp: str
