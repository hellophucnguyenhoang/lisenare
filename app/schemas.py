from sqlmodel import SQLModel
import re


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

class EventUpdate(SQLModel):
    event_type: str

class Submition(SQLModel):
    user_answer: str

class RecommendedItem(SQLModel):
    study_session_id: int
    batch_id: str
    item: "ReadingRead"

class ReadingBase(SQLModel):
    topic_id: int
    title: str
    content_text: str
    difficulty: int
    num_words: int | None = None
    num_questions: int | None = None
    questions: list["ObjectiveQuestionRead"] = []

    @property
    def num_words(self) -> int:
        """
        Automatically calculate number of words in title + content_text
        """
        text = f"{self.title} {self.content_text}"
        words = re.findall(r"\b\w+\b", text)
        return len(words)
    
class ReadingRead(ReadingBase):
    id: int
    
class ObjectiveQuestionBase(SQLModel):
    reading_id: int
    question_text: str
    option_a: str
    option_b: str | None = None
    option_c: str | None = None
    option_d: str | None = None
    correct_option: int
    explanation: str | None = None
    order_index: int | None = None


class ObjectiveQuestionRead(ObjectiveQuestionBase):
    id: int