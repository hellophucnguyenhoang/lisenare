from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship, create_engine


class UserTopicLink(SQLModel, table=True):
    __tablename__ = "user_topic_link"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    topic_id: int = Field(foreign_key="topics.id", primary_key=True)


class Topic(SQLModel, table=True):
    __tablename__ = "topics"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(description='e.g., "Science", "Travel", "Health"')

    users: list["User"] = Relationship(back_populates="topic_preferences", link_model=UserTopicLink)
    readings: list["Reading"] = Relationship(back_populates="topic")


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str
    hashed_password: str

    email: str | None = None
    user_level: int | None = Field(default=None, description="e.g., 0-5 (A1-C2)")
    goal_type: int | None = Field(default=None, description="e.g., 0-3 (Exam prep, Casual, Career, Other)")
    age_group: int | None = Field(default=None, description="e.g., 0: Children, 1: Teenagers, 1: Adults")
    last_login: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    topic_preferences: list["Topic"] = Relationship(back_populates="users", link_model=UserTopicLink)
    study_sessions: list["StudySession"] = Relationship(back_populates="user")
    user_state: "UserState" = Relationship(back_populates="user")


class UserState(SQLModel, table=True):
    __tablename__ = "user_states"

    id: int | None = Field(default=None, primary_key=True)
    item_ids: str = Field(default="", description="Comma-separated item IDs, e.g. '1,2,8,3,2'")

    user_id: int = Field(foreign_key="users.id")
    user: User = Relationship(back_populates="user_state")
    interactions: list["Interaction"] = Relationship(back_populates="user_state")


class Reading(SQLModel, table=True):
    __tablename__ = "readings"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    content_text: str
    difficulty: int
    estimated_time: int | None = Field(default=None, description="Minutes")
    num_questions: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    topic_id: int = Field(foreign_key="topics.id")

    topic: Topic = Relationship(back_populates="readings")
    questions: list["ObjectiveQuestion"] = Relationship(back_populates="reading")
    study_sessions: list["StudySession"] = Relationship(back_populates="reading")
    interactions: list["Interaction"] = Relationship(back_populates="item")


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
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    rating: int = Field(default=0, ge=-1, le=1, description="0: neutral, -1: dislike, 1: like")
    time_spent: float = Field(default=0, ge=0, le=100, description="Minutes")
    give_up: bool = False
    user_answers: str = Field(default="", description="e.g., 0,1,2,0")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user_id: int = Field(foreign_key="users.id")
    reading_id: int = Field(foreign_key="readings.id")
    
    user: User | None = Relationship(back_populates="study_sessions")
    reading: Reading | None = Relationship(back_populates="study_sessions")


class Interaction(SQLModel, table=True):
    __tablename__ = "interactions"

    id: int | None = Field(default=None, primary_key=True)
    event_type: str
    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    user_state_id: int = Field(foreign_key="user_states.id")
    item_id: int = Field(foreign_key="readings.id")

    user_state: UserState = Relationship(back_populates="interactions")
    item: Reading = Relationship(back_populates="interactions")
