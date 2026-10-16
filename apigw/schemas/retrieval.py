from pydantic import BaseModel, Field


class StartRetrievalRequest(BaseModel):
    learner_id: int
    topic_ids: list[int] = Field(min_length=1)


class AnswerRetrievalRequest(BaseModel):
    session_id: str
    learner_id: int
    question_id: int
    learner_answer: str


class EndRetrievalRequest(BaseModel):
    session_id: str
    learner_id: int


class RetrievalQuestionResponse(BaseModel):
    id: int
    question: str | None = None
    content: str | None = None
    answer: str | None = None
    type: str | None = None
    difficulty: float


class StartRetrievalResponse(BaseModel):
    session_id: str
    theta: float
    question: RetrievalQuestionResponse


class AnswerRetrievalResponse(BaseModel):
    is_correct: bool
    correct_answer: str | None = None
    theta: float
    retrieval_completed: bool
    next_question: RetrievalQuestionResponse | None = None
