from pydantic import BaseModel, Field


class StartPracticeRequest(BaseModel):
    learner_id: int
    topic_ids: list[int] = Field(min_length=1)


class AnswerPracticeRequest(BaseModel):
    session_id: str
    learner_id: int
    question_id: int
    learner_answer: str


class EndPracticeRequest(BaseModel):
    session_id: str
    learner_id: int


class PracticeQuestionResponse(BaseModel):
    id: int
    question: str | None = None
    content: str | None = None
    answer: str | None = None
    type: str | None = None
    difficulty: float


class StartPracticeResponse(BaseModel):
    session_id: str
    theta: float
    question: PracticeQuestionResponse


class AnswerPracticeResponse(BaseModel):
    is_correct: bool
    correct_answer: str | None = None
    theta: float
    practice_completed: bool
    next_question: PracticeQuestionResponse | None = None
