from sqlmodel import SQLModel
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
# Model nhận data từ FE (không lưu DB trực tiếp)
class AnswerRecord(SQLModel):
    question_id: int
    user_answer: str
    time_seconds: int

class SubmitRequest(SQLModel):
    user_id: int
    exercise_id: int
    submitted_at: datetime
    answers: list[AnswerRecord]

class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class QuestionContext(BaseModel):
    question_id: int
    question: str
    user_answer: Optional[str] = None

class Context(BaseModel):
    exercise_id: int
    exercise_name: str
    questions: list[QuestionContext]

class ChatRequest(BaseModel):
    messages: list[Message]
    learner_id: int
    context: Context

class SuggestRequest(BaseModel):
    learner_id: int
    context: Context
    question_hinted: QuestionContext

def get_answered_questions(request: ChatRequest | SuggestRequest) -> list[QuestionContext]:
    return [q for q in request.context.questions if q.user_answer is not None]

