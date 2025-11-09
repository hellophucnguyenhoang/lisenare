from sqlmodel import Session, select
from app.models import Reading, ObjectiveQuestion
from app.schemas import ReadingCreate, ObjectiveQuestionCreate
import random

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

def get_random_reading(session: Session) -> Reading | None:
    reading_ids = session.exec(select(Reading.id)).all()
    if not reading_ids:
        return None
    random_id = random.choice(reading_ids)
    return session.get(Reading, random_id)

def get_random_unseen_reading(session: Session, excluded_ids: list[int]) -> Reading:
    """
    Get a random reading that is NOT in excluded_ids.
    If all readings are already interacted, return any reading and log a warning.
    """
    stmt = select(Reading)
    if excluded_ids:
        stmt = stmt.where(Reading.id.not_in(excluded_ids))

    available_readings = session.exec(stmt).all()
    if not available_readings:
        # fallback: all readings are interacted, pick any reading
        all_readings = session.exec(select(Reading)).all()
        if not all_readings:
            raise ValueError("No readings found in the database")
        print("User has interacted with all readings. Returning a random reading anyway.")
        return random.choice(all_readings)

    return random.choice(available_readings)