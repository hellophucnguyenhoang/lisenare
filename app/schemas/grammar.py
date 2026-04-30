from sqlmodel import SQLModel
from datetime import datetime

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