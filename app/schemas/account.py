from sqlmodel import Field, SQLModel


class LearnerAccountCreate(SQLModel):
    full_name: str = "The Avid Learner"
    username: str = Field(default="qwerwert", min_length=8)
    password: str = Field(default="kcmtl5cM#", min_length=8)
    email: str | None = None


class PasswordChangeRequest(SQLModel):
    old_password: str
    new_password: str


class PasswordResetRequest(SQLModel):
    username: str
    new_password: str = Field(min_length=8)
    otp: str
