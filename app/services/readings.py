from sqlmodel import Session, select
from app.models import Reading, ObjectiveQuestion
from app.schemas import ReadingCreate, ObjectiveQuestionCreate
from typing import List

def create_reading(session: Session, reading_create: ReadingCreate) -> Reading:
    reading = Reading.model_validate(reading_create)
    session.add(reading)
    session.commit()
    session.refresh(reading)
    return reading

def add_objective_question(session: Session, question_create: ObjectiveQuestionCreate) -> ObjectiveQuestion:
    question = ObjectiveQuestion.model_validate(question_create)
    session.add(question)
    session.commit()
    session.refresh(question)
    return question

def get_all_readings(session: Session) -> List[Reading]:
    topics = session.exec(select(Reading)).all()
    return topics