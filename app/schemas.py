from sqlmodel import SQLModel
from typing import List, Optional
from datetime import datetime


# ---- User ----
class UserBase(SQLModel):
    username: str
    email: str
    user_level: Optional[int] = 0
    goal_type: Optional[int] = 0
    age_group: Optional[int] = 0

class UserCreate(UserBase):
    password: str  # raw password; service should hash it

class UserRead(UserBase):
    id: int


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
    content_text: Optional[str] = None
    difficulty: Optional[int] = None
    estimated_time: Optional[int] = None
    num_questions: Optional[int] = 4

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
    rating: int = 3
    time_spent: Optional[float] = None
    give_up: bool = False

class StudySessionCreate(StudySessionBase):
    pass

class StudySessionRead(StudySessionBase):
    id: int
    completed_at: datetime