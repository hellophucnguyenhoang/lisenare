from sqlmodel import SQLModel, Field
from typing import List, Optional, Literal
from datetime import datetime


# ---- User ----
class UserBase(SQLModel):
    username: str
    email: Optional[str] = None
    user_level: Optional[int] = 0
    goal_type: Optional[int] = 0
    age_group: Optional[int] = 0

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


# ---- Topic ----
class TopicCreate(SQLModel):
    name: str

class TopicRead(SQLModel):
    id: int
    name: str


# ---- Reading ----
class ReadingBase(SQLModel):
    topic_id: int
    title: str
    content_text: str
    difficulty: int
    estimated_time: int
    num_questions: int = 4
    questions: List["ObjectiveQuestionRead"] = []

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
    explanation: Optional[str] = None
    order_index: Optional[int] = None

class ObjectiveQuestionCreate(ObjectiveQuestionBase):
    pass

class ObjectiveQuestionRead(ObjectiveQuestionBase):
    id: int


# ---- StudySession ----
class StudySessionBase(SQLModel):
    user_id: int
    reading_id: int
    score: float = 0.0
    rating: int = Field(default=0, ge=-1, le=1)
    time_spent: Optional[float] = None
    give_up: bool = False
    user_answers: Optional[str] = None

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
    explanation: Optional[str]
    user_selected: Optional[int]  # user's chosen option index or None
    is_correct: bool

class StudySessionResult(SQLModel):
    id: int
    user_id: int
    reading_id: int
    score: float
    rating: int
    time_spent: Optional[float]
    give_up: bool
    user_answers: Optional[str]
    completed_at: datetime
    reading_title: str
    reading_content: Optional[str]
    questions: List[QuestionResult]

class RatingUpdate(SQLModel):
    rating: int = Field(default=0, ge=-1, le=1)


class InteractionCreate(SQLModel):
    user_id: Optional[int]
    item_id: int
    event_type: str
    event_time: Optional[datetime] = None


class RecommendItemRequest(SQLModel):
    username: str = "anonymous"

class RecommendItemResponse(SQLModel):
    item: ReadingRead
