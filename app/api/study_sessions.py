from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional

from app.database import get_session
from app.schemas import StudySessionCreate, StudySessionRead, StudySessionResult
from app.models import Reading, ObjectiveQuestion, StudySession
from app.services import study_sessions as study_session_service

router = APIRouter(prefix="/study_sessions", tags=["StudySessions"])


# @router.post("/", response_model=StudySessionRead)
# def record_study_session_api(study_session: StudySessionCreate, session: Session = Depends(get_session)):
#     return study_session_service.record_study_session(session, study_session)

@router.post("/", response_model=StudySessionResult)
def create_study_session(session_in: StudySessionCreate, session: Session = Depends(get_session)):
    # Fetch reading and its questions
    reading = session.exec(
        select(Reading).where(Reading.id == session_in.reading_id)
    ).first()
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")

    # Get questions ordered (use order_index if present, else id)
    questions = session.exec(
        select(ObjectiveQuestion).where(ObjectiveQuestion.reading_id == reading.id)
    ).all()
    # sort by order_index or id
    questions.sort(key=lambda q: (q.order_index if q.order_index is not None else q.id))

    # Parse user_answers (CSV of ints) -> list[int]
    parsed_answers: List[Optional[int]] = []
    if session_in.user_answers:
        # allow both "0,1,2" and whitespace
        entries = [s.strip() for s in session_in.user_answers.split(",") if s.strip() != ""]
        for e in entries:
            try:
                parsed_answers.append(int(e))
            except ValueError:
                parsed_answers.append(None)
    # If fewer answers than questions, fill with None
    while len(parsed_answers) < len(questions):
        parsed_answers.append(None)

    # Compute correct count
    correct_count = 0
    for q, user_sel in zip(questions, parsed_answers):
        if user_sel is not None and user_sel == q.correct_option:
            correct_count += 1
    total = len(questions) if len(questions) > 0 else 1
    score = correct_count / total

    # Create StudySession model and save (we override score)
    study_session = StudySession(
        user_id=session_in.user_id,
        reading_id=session_in.reading_id,
        score=score,
        rating=session_in.rating,
        time_spent=session_in.time_spent,
        give_up=session_in.give_up,
        user_answers=",".join(str(x) if x is not None else "" for x in parsed_answers)
    )
    session.add(study_session)
    session.commit()
    session.refresh(study_session)

    # Build response (StudySessionResult)
    q_results = []
    for q, user_sel in zip(questions, parsed_answers):
        q_results.append({
            "id": q.id,
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": q.correct_option,
            "explanation": q.explanation,
            "user_selected": user_sel,
            "is_correct": (user_sel is not None and user_sel == q.correct_option)
        })

    result = StudySessionResult(
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
        questions=q_results
    )

    return result


@router.get("/{session_id}", response_model=StudySessionResult)
def get_study_session_result(session_id: int, db: Session = Depends(get_session)):
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

    # parse stored csv into list
    parsed_answers: List[Optional[int]] = []
    if db_session.user_answers:
        entries = [s.strip() for s in db_session.user_answers.split(",") if s.strip() != ""]
        for e in entries:
            try:
                parsed_answers.append(int(e))
            except ValueError:
                parsed_answers.append(None)
    while len(parsed_answers) < len(questions):
        parsed_answers.append(None)

    q_results = []
    for q, user_sel in zip(questions, parsed_answers):
        q_results.append({
            "id": q.id,
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": q.correct_option,
            "explanation": q.explanation,
            "user_selected": user_sel,
            "is_correct": (user_sel is not None and user_sel == q.correct_option)
        })

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


@router.patch("/{session_id}/rating")
def update_rating(session_id: int, rating: int, db: Session = Depends(get_session)):
    db_session = db.get(StudySession, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Study session not found")
    db_session.rating = rating
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return {"ok": True, "rating": db_session.rating}

