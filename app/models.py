from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship, create_engine
import re
import uuid

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
    preference_emb: bytes


class Reading(SQLModel, table=True):
    __tablename__ = "readings"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    content_text: str
    difficulty: int
    num_questions: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    topic_id: int = Field(foreign_key="topics.id")

    topic: Topic = Relationship(back_populates="readings")
    questions: list["ObjectiveQuestion"] = Relationship(back_populates="reading")
    study_sessions: list["StudySession"] = Relationship(back_populates="reading")
    reading_embedding: "ReadingEmbedding" = Relationship(back_populates="reading")

    @property
    def num_words(self) -> int:
        """
        Automatically calculate number of words in title + content_text
        """
        text = f"{self.title} {self.content_text}"
        words = re.findall(r"\b\w+\b", text)
        return len(words)


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
    user_answers: str = Field(default="", description="e.g., 0,-1,2,1, means user answered AxCB")
    last_event_type: str | None = None
    
    # a recommendation is made from a specific user state,
    # but we have to recommend a batch for performance reason
    # so we recommend a batch instead of a item, for 1 recommendation, and later
    # only get the item with the highest event reward in a batch as if 
    # it's just 1 item recommendation when process the data for training further
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    last_update: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # similarity between user_preference vector and the item embedding at the recommendation time
    sim01: float 

    user_id: int = Field(foreign_key="users.id")
    reading_id: int = Field(foreign_key="readings.id")
    
    user: User | None = Relationship(back_populates="study_sessions")
    reading: Reading | None = Relationship(back_populates="study_sessions")



# Item embedding
class ReadingEmbedding(SQLModel, table=True):
    __tablename__ = "reading_embeddings"

    id: int | None = Field(default=None, primary_key=True)
    reading_id: int = Field(foreign_key="readings.id", unique=True)
    vector_blob: bytes

    reading: Reading = Relationship(back_populates="reading_embedding")
