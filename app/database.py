from typing import Iterator
from sqlmodel import SQLModel, Field, Relationship, create_engine, Session
from datetime import datetime, timezone
from pydantic import EmailStr
from .config import settings

class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id", unique=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    email: EmailStr = Field(index=True, unique=True)
    last_login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    learner: "Learner" = Relationship(back_populates="account")

class Learner(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    full_name: str
    cerf_level: str
    bricks: list["Brick"] = Relationship(back_populates="learner")
    study_sessions: list["StudySession"] = Relationship(back_populates="learner")
    account: Account | None = Relationship(back_populates="learner") # Allow null in runtime

class Brick(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    creator_id: int | None = Field(default=None, foreign_key="learner.id")
    native_text: str
    target_text: str
    target_audio_url: str
    is_public: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    learner: Learner | None = Relationship(back_populates="bricks")
    study_sessions: list["StudySession"] = Relationship(back_populates="brick")

class StudySession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    brick_id: int = Field(foreign_key="brick.id")
    user_target_text: str | None = None
    user_target_audio_url: str | None = None
    enrolled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    learner: Learner = Relationship(back_populates="study_sessions")
    brick: Brick = Relationship(back_populates="study_sessions")

sqlite_url = f"sqlite:///{settings.db_url}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
