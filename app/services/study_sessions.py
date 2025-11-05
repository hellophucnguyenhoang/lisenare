from sqlmodel import Session, select
from app.models import StudySession, Reading, ObjectiveQuestion
from app.schemas import StudySessionCreate, StudySessionResult, RatingUpdate
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException


def record_study_session(session: Session, session_create: StudySessionCreate) -> StudySession:
    study_session = StudySession.model_validate(session_create)
    session.add(study_session)
    session.commit()
    session.refresh(study_session)
    return study_session

def parse_user_answers(user_answers: Optional[str], question_count: int) -> List[Optional[int]]:
    """Parse CSV user answers string into a list of integers/None."""
    parsed = []
    if user_answers:
        entries = [s.strip() for s in user_answers.split(",") if s.strip() != ""]
        for e in entries:
            try:
                parsed.append(int(e))
            except ValueError:
                parsed.append(None)
    while len(parsed) < question_count:
        parsed.append(None)
    return parsed


def create_study_session(db: Session, session_in: StudySessionCreate) -> StudySessionResult:
    reading = db.exec(select(Reading).where(Reading.id == session_in.reading_id)).first()
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")

    questions = db.exec(
        select(ObjectiveQuestion).where(ObjectiveQuestion.reading_id == reading.id)
    ).all()
    questions.sort(key=lambda q: (q.order_index if q.order_index is not None else q.id))

    parsed_answers = parse_user_answers(session_in.user_answers, len(questions))

    correct_count = sum(
        1 for q, ans in zip(questions, parsed_answers)
        if ans is not None and ans == q.correct_option
    )
    total = len(questions) or 1
    score = correct_count / total

    study_session = StudySession(
        user_id=session_in.user_id,
        reading_id=session_in.reading_id,
        score=score,
        rating=session_in.rating,
        time_spent=session_in.time_spent,
        give_up=session_in.give_up,
        user_answers=",".join(str(x) if x is not None else "" for x in parsed_answers)
    )
    db.add(study_session)
    db.commit()
    db.refresh(study_session)

    question_results = [
        {
            "id": q.id,
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": q.correct_option,
            "explanation": q.explanation,
            "user_selected": ans,
            "is_correct": ans is not None and ans == q.correct_option
        }
        for q, ans in zip(questions, parsed_answers)
    ]

    return StudySessionResult(
        id=study_session.id,
        user_id=study_session.user_id,
        reading_id=study_session.reading_id,
        score=study_session.score,
        rating=study_session.rating,
        time_spent=study_session.time_spent,
        give_up=study_session.give_up,
        user_answers=study_session.user_answers,
        completed_at=study_session.completed_at,
        reading_title=reading.title,
        reading_content=reading.content_text,
        questions=question_results
    )


def get_study_session_result(db: Session, session_id: int) -> StudySessionResult:
    db_session = db.get(StudySession, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Study session not found")

    reading = db.get(Reading, db_session.reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")

    questions = db.exec(
        select(ObjectiveQuestion).where(ObjectiveQuestion.reading_id == reading.id)
    ).all()
    questions.sort(key=lambda q: (q.order_index if q.order_index is not None else q.id))

    parsed_answers = parse_user_answers(db_session.user_answers, len(questions))

    q_results = [
        {
            "id": q.id,
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": q.correct_option,
            "explanation": q.explanation,
            "user_selected": ans,
            "is_correct": ans is not None and ans == q.correct_option
        }
        for q, ans in zip(questions, parsed_answers)
    ]

    return StudySessionResult(
        id=db_session.id,
        user_id=db_session.user_id,
        reading_id=db_session.reading_id,
        score=db_session.score,
        rating=db_session.rating,
        time_spent=db_session.time_spent,
        give_up=db_session.give_up,
        user_answers=db_session.user_answers,
        completed_at=db_session.completed_at,
        reading_title=reading.title,
        reading_content=reading.content_text,
        questions=q_results
    )


def update_rating(db: Session, session_id: int, payload: RatingUpdate):
    db_session = db.get(StudySession, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Study session not found")
    db_session.rating = payload.rating
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return {"ok": True, "rating": db_session.rating}