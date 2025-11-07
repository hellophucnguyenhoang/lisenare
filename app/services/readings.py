from sqlmodel import Session, select
from app.models import Reading, ObjectiveQuestion
from app.schemas import ReadingCreate, ObjectiveQuestionCreate

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

def get_all_readings(session: Session) -> list[Reading]:
    readings = session.exec(select(Reading)).all()
    return readings

def get_full_reading_by_id(session: Session, id: int):
    return session.exec(select(Reading).where(Reading.id == id)).one()

def get_readings_by_ids(session: Session, item_ids: list[int]) -> list[Reading]:
    if not item_ids:
        return []
    stmt = select(Reading).where(Reading.id.in_(item_ids))
    readings = session.exec(stmt).all()
    return readings
