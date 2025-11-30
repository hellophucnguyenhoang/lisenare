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
    preference_topic_ids: list[int] = []

class UserRead(UserBase):
    id: int
    preference_topics: list["TopicRead"] = []

class UserUpdate(SQLModel):
    email: str | None = None
    user_level: int | None = None
    goal_type: int | None = None
    age_group: int | None = None
    preference_topic_ids: list[int] | None = None


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
    topic_name: str | None = None # none only for ReadingRead contruction
    
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

class TopicRead(SQLModel):
    id: int
    name: str

# COEDIT
# Request body
class WritingCheckRequest(SQLModel):
    instruction: str = "Fix the grammar"
    text: str

class WritingCheckResponse(SQLModel):
    edited_text: str
    total_sentences: int

class CEFRClassificationRequest(SQLModel):
    text: str

class CEFRClassificationResponse(SQLModel):
    cefr_index: int
    cefr_label: str

# Context Search
# Request model
class ContextSearchRequest(SQLModel):
    query: str
    n_results: int = 10  # optional

class ContextSearchResult(SQLModel):
    url: str
    text: str
    start: float

# The top-level response is a list of SearchResult objects
ContextSearchResponse = list[ContextSearchResult]