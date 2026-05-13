from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.database import HistoryAnswerQuestion, Lesson, get_session
from app.schemas import (
    ChatRequest,
    QuestionContext,
    QuestionInput,
    RLMOutput,
    RuntimeSession,
    SubmitRequest,
    SuggestRequest,
    get_answered_questions,
)
from app.services.chatbot_service import get_hint_stream
from app.services.history_answer_question_service import (
    get_difficulty_and_respone,
    insert_list_history_answer_question,
)
from app.services.lesson_service import (
    get_lesson_by_exercise,
    get_lesson_by_question,
)
from app.services.question_service import (
    evaluate_questions,
    get_question_by_exercise_id,
    get_question_by_id,
    process_questions,
)
from app.services.rlm_service import run_rlm
from app.services.theta_learner_lesson_service import (
    computeP,
    get_theta_by_leaner_and_lesson,
    insert_or_update_theta,
    update_theta,
)
from app.services.topic_service import build_learning_tree

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
def submit_exercise(
    data: SubmitRequest, session: Session = Depends(get_session)
):
    time = datetime.now()
    records = [
        HistoryAnswerQuestion(
            learner_id=data.user_id,
            question_id=ans.question_id,
            user_answer=ans.user_answer,
            timesecond=time,
        )
        for ans in data.answers
    ]
    lesson = get_lesson_by_question(
        session, question_id=records[0].question_id
    )
    insert_list_history_answer_question(session, records)
    insert_or_update_theta(
        session=session, learner_id=data.user_id, lesson_id=lesson.id
    )
    return {"message": "Nộp bài thành công và đã thêm vào database"}


@router.post("/chat")
def grammar_chat(
    body: ChatRequest, session: Session = Depends(get_session)
) -> StreamingResponse:
    print(f"body: {body}")
    exercise_id = body.context.exercise_id
    lesson = get_lesson_by_exercise(session=session, exercise_id=exercise_id)
    lesson_name = lesson.name
    questions = [
        convert_content_to_input(question, session=session)
        for question in body.context.questions
    ]
    insert_or_update_theta(
        session, learner_id=body.learner_id, lesson_id=lesson.id
    )
    theta = get_theta_by_leaner_and_lesson(
        session, learner_id=body.learner_id, lesson_id=lesson.id
    )
    history = body.messages
    current_question_id = body.context.current_question_id
    rlm_input = RuntimeSession(
        questions, lesson_name, theta, history, current_question_id
    )
    question = body.messages[-1].content
    answer = run_rlm(question, rlm_input)
    print(f"current question id: {rlm_input.current_question_id}")
    return RLMOutput(
        answer=answer, current_question_id=rlm_input.current_question_id
    )


@router.post("/suggest")
def suggest_answer(
    body: SuggestRequest, session: Session = Depends(get_session)
) -> StreamingResponse:
    question_target = body.question_hinted
    question = get_question_by_id(
        session=session, id=question_target.question_id
    )
    question_content = question_target.question
    correct_answer = question.correct_answer
    choice = question.answer
    theta_new, prob, lesson = resolve_theta_and_prob(body, session, question)
    return StreamingResponse(
        get_hint_stream(
            theta=theta_new,
            prob=prob,
            lesson=lesson.name,
            question=question_content,
            correct_answer=correct_answer,
            choice=choice,
        ),
        media_type="text/plain",
    )


def resolve_theta_and_prob(
    body, session, question
) -> tuple[float, float, Lesson]:
    lesson = get_lesson_by_exercise(
        session, exercise_id=body.context.exercise_id
    )
    insert_or_update_theta(
        session, learner_id=body.learner_id, lesson_id=lesson.id
    )
    theta = get_theta_by_leaner_and_lesson(
        session, learner_id=body.learner_id, lesson_id=lesson.id
    )
    db_items, db_responds = get_difficulty_and_respone(
        session, lesson.id, learner_id=body.learner_id
    )
    items, responds = evaluate_questions(
        questions=get_answered_questions(body), session=session
    )
    theta_new = update_theta(
        theta, items=db_items + items, responses=db_responds + responds
    )
    prob = computeP(theta_new, 1, b=question.difficulty)
    return theta_new, prob, lesson


def convert_content_to_input(question: QuestionContext, session: Session):
    id = question.question_id
    question_input = get_question_by_id(session=session, id=id)
    return QuestionInput(
        id=question_input.id,
        order_id=question.order_id,
        question=question_input.question,
        answer=question_input.answer,
        type=question_input.type,
        correct_answer=question_input.correct_answer,
        difficulty=question_input.difficulty,
    )
