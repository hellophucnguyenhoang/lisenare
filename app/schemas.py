from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
import re

# ---- Topic ----
class TopicCreate(SQLModel):
    name: str

class TopicRead(SQLModel):
    id: int
    name: str


# ---- User and Auth/Token ----
class UserBase(SQLModel):
    username: str
    email: str | None = None
    user_level: int | None = 0
    goal_type: int | None = 0
    age_group: int | None = 0

class UserCreate(UserBase):
    password: str  # raw password; service should hash it

class UserRead(UserBase):
    id: int

class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"

class UserWithToken(SQLModel):
    user: UserRead
    token: Token


# --- User State ---
class UserStateBase(SQLModel):
    item_ids: str = "" # e.g., "21,11,34,5"
    user_id: int

class UserStateRead(UserStateBase):
    id: int


# ---- Reading ----
class ReadingBase(SQLModel):
    topic_id: int
    title: str
    content_text: str
    difficulty: int
    num_words: int = Field(ge=3)
    num_questions: int = 1
    questions: list["ObjectiveQuestionRead"] = []

    @property
    def num_words(self) -> int:
        """
        Automatically calculate number of words in title + content_text
        """
        text = f"{self.title} {self.content_text}"
        words = re.findall(r"\b\w+\b", text)
        return len(words)

class ReadingCreate(ReadingBase):
    pass

class ReadingRead(ReadingBase):
    id: int
    created_at: datetime


# ---- Objective Question ----
class ObjectiveQuestionBase(SQLModel):
    reading_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: int
    explanation: str | None = None
    order_index: int | None = None

class ObjectiveQuestionCreate(ObjectiveQuestionBase):
    pass

class ObjectiveQuestionRead(ObjectiveQuestionBase):
    id: int


# ---- StudySession ----
class StudySessionBase(SQLModel):
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    rating: int = Field(default=0, ge=-1, le=1)
    time_spent: float = Field(default=0, ge=0, le=100, description="Minutes")
    give_up: bool = False
    user_answers: str = ""
    user_id: int
    reading_id: int

class StudySessionCreate(StudySessionBase):
    pass

class StudySessionRead(StudySessionBase):
    id: int
    completed_at: datetime


class QuestionResult(SQLModel):
    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str | None = None
    correct_option: int
    explanation: str | None
    user_selected: int | None  # user's chosen option index or None
    is_correct: bool

class StudySessionResult(SQLModel):
    id: int
    user_id: int
    reading_id: int
    score: float
    rating: int
    time_spent: float | None
    give_up: bool
    user_answers: str | None
    completed_at: datetime
    reading_title: str
    reading_content: str | None
    questions: list[QuestionResult]

class RatingUpdate(SQLModel):
    rating: int = Field(default=0, ge=-1, le=1)

# ------ Recommendation and Interaction ----------
class InteractionCreate(SQLModel):
    event_type: str
    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_state_id: int
    item_id: int


class RecommendItemRequest(SQLModel):
    username: str = "anonymous"

class RecommendItemResponse(SQLModel):
    user_state: UserStateRead
    item: ReadingRead
