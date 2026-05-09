from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.schemas import SubmitRequest, ChatRequest, get_answered_questions, SuggestRequest
from app.database import HistoryAnswerQuestion, Lesson
from app.database import get_session
from datetime import datetime
from app.services.question_service import (
    get_question_by_exercise_id,
    process_questions, get_question_by_id, evaluate_questions
)
from app.services.topic_service import build_learning_tree
from app.services.history_answer_question_service import insert_list_history_answer_question, get_difficulty_and_respone
from app.services.theta_learner_lesson_service import insert_or_update_theta, get_theta_by_leaner_and_lesson, update_theta, computeP
from app.services.lesson_service import get_lesson_by_question, get_lesson_by_exercise
from app.services.chatbot_service import find_target_question, get_hint, get_hint_stream
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/grammar", tags=["Grammars"])


@router.get("/topics")
def get_topics(session: Session = Depends(get_session)):
    # trả về list topics kèm lessons và exercises lồng nhau
    return build_learning_tree(session)


@router.get("/questions/{exercise_id}")
def get_questions(exercise_id: int, session: Session = Depends(get_session)):
    questions = []
    for question in get_question_by_exercise_id(session, exercise_id):
        questions.append(process_questions(question))
    return questions

@router.post("/submit")
def submit_exercise(data : SubmitRequest, session: Session = Depends(get_session)):
    time = datetime.now()
    records = [
        HistoryAnswerQuestion(
            learner_id=data.user_id,
            question_id=ans.question_id,
            user_answer=ans.user_answer,
            timesecond = time
        )
        for ans in data.answers
    ]
    lesson = get_lesson_by_question(session, question_id=records[0].question_id)
    insert_list_history_answer_question(session, records)
    insert_or_update_theta(session=session, learner_id=data.user_id, lesson_id=lesson.id)
    return {"message": "Nộp bài thành công và đã thêm vào database"}

@router.post("/chat")
def grammar_chat(body: ChatRequest, session: Session = Depends(get_session)) -> StreamingResponse:
    question_target = find_target_question(body.messages, body.context.questions)
    question = get_question_by_id(session=session, id = question_target.question_id)
    question_content = question_target.question
    correct_answer = question.correct_answer
    choice = question.answer
    theta_new, prob, lesson = resolve_theta_and_prob(body, session, question)
    return StreamingResponse(
        get_hint_stream(theta=theta_new, prob=prob, lesson=lesson.name, question=question_content, correct_answer=correct_answer, choice=choice),
        media_type="text/plain"
    )

@router.post("/suggest")
def suggest_answer(body: SuggestRequest, session: Session = Depends(get_session)) -> StreamingResponse:
    question_target = body.question_hinted
    question = get_question_by_id(session=session, id = question_target.question_id)
    question_content = question_target.question
    correct_answer = question.correct_answer
    choice = question.answer
    theta_new, prob, lesson = resolve_theta_and_prob(body, session, question)
    return StreamingResponse(
        get_hint_stream(theta=theta_new, prob=prob, lesson=lesson.name, question=question_content, correct_answer=correct_answer, choice=choice),
        media_type="text/plain"
    )
    
def resolve_theta_and_prob(body, session, question) -> tuple[float, float, Lesson]:
    lesson = get_lesson_by_exercise(session, exercise_id=body.context.exercise_id)
    insert_or_update_theta(session, learner_id=body.learner_id, lesson_id=lesson.id)
    theta = get_theta_by_leaner_and_lesson(session, learner_id=body.learner_id, lesson_id=lesson.id)
    db_items, db_responds = get_difficulty_and_respone(session, lesson.id, learner_id=body.learner_id)
    items, responds = evaluate_questions(questions=get_answered_questions(body), session=session)
    theta_new = update_theta(theta, items=db_items + items, responses=db_responds + responds)
    prob = computeP(theta_new, 1, b=question.difficulty)
    return theta_new, prob, lesson