from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship, create_engine
from typing import Optional, Literal

class UserTopicLink(SQLModel, table=True):
    __tablename__ = "user_topic_link"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    topic_id: int = Field(foreign_key="topics.id", primary_key=True)


class Topic(SQLModel, table=True):
    __tablename__ = "topics"

    id: int | None = Field(default=None, primary_key=True)
    name: str  # e.g., "Science", "Travel", "Health"

    users: list["User"] = Relationship(back_populates="topic_preferences", link_model=UserTopicLink)
    readings: list["Reading"] = Relationship(back_populates="topic")


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str
    hashed_password: str
    email: str | None = None
    user_level: int | None = Field(default=0, description="0-5 (A1-C2)")
    goal_type: int | None = Field(default=0, description="0-3 (Exam prep, Casual, Career, Other)")
    age_group: int | None = Field(default=0, description="0: Teenagers, 1: Adult")
    last_login: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    topic_preferences: list["Topic"] = Relationship(back_populates="users", link_model=UserTopicLink)
    study_sessions: list["StudySession"] = Relationship(back_populates="user")


class Reading(SQLModel, table=True):
    __tablename__ = "readings"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topics.id")
    title: str
    content_text: str | None = Field(default=None, description="Full reading passage")
    difficulty: int
    estimated_time: int | None = Field(default=None, description="Minutes")
    num_questions: int | None = Field(default=4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    topic: Topic = Relationship(back_populates="readings")
    questions: list["ObjectiveQuestion"] = Relationship(back_populates="reading")
    study_sessions: list["StudySession"] = Relationship(back_populates="reading")


class ObjectiveQuestion(SQLModel, table=True):
    __tablename__ = "objective_questions"

    id: int | None = Field(default=None, primary_key=True)
    reading_id: int = Field(foreign_key="readings.id")
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str | None = None
    correct_option: int = Field(ge=0, le=3) # 0, 1, 2, 3
    explanation: str | None = None
    order_index: int | None = None

    # Relationships
    reading: Reading | None = Relationship(back_populates="questions")


class StudySession(SQLModel, table=True):
    __tablename__ = "study_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    reading_id: int = Field(foreign_key="readings.id")
    score: float = Field(default=0.0, ge=0.0, le=1.0)  # 0 to 1
    rating: int = Field(default=0, ge=-1, le=1)
    time_spent: float | None = Field(default=None, ge=0, le=100)
    give_up: bool = Field(default=False)
    user_answers: Optional[str] = None  # store like "0,1,2,0"
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    user: User | None = Relationship(back_populates="study_sessions")
    reading: Reading | None = Relationship(back_populates="study_sessions")


class Interaction(SQLModel, table=True):
    __tablename__ = "interactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, index=True)
    item_id: int = Field(index=True)
    event_type: str
    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
