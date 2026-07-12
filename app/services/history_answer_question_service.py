import string
import threading
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.database import (
    Exercise,
    HistoryAnswerQuestion,
    Learner,
    Lesson,
    Question,
    Topic,
)


def insert_history_answer_question(
    session: Session, historyanswerquestion: HistoryAnswerQuestion
):
    try:
        session.add(historyanswerquestion)
        session.commit()
        _fire_analysis_trigger(historyanswerquestion.learner_id)
    except Exception as e:
        session.rollback()
        print(f"Lỗi khi thêm lịch sử: {e}")


def insert_list_history_answer_question(
    session: Session, listhistoryanswerquestion: list[HistoryAnswerQuestion]
):
    try:
        for history in listhistoryanswerquestion:
            session.add(history)
        session.commit()
        print("Thêm lịch sử thành công")
        for lid in {h.learner_id for h in listhistoryanswerquestion}:
            _fire_analysis_trigger(lid)
    except Exception as e:
        session.rollback()
        print(f"Lỗi khi thêm list historyanswerquestion vào database:{e}")


def _fire_analysis_trigger(learner_id: int) -> None:
    from app.services.wrong_analysis_service import trigger_analysis_if_milestone
    threading.Thread(
        target=trigger_analysis_if_milestone,
        args=(learner_id,),
        daemon=True,
    ).start()


def get_history_by_learner_and_lesson(
    session: Session, lesson_id: int, learner_id: int
):
    statement = (
        select(
            HistoryAnswerQuestion.id,
            HistoryAnswerQuestion.timesecond,
            Question.correct_answer,
            HistoryAnswerQuestion.user_answer,
            Question.difficulty,
        )
        .join(Question, HistoryAnswerQuestion.question_id == Question.id)
        .join(Exercise, Question.exercise_id == Exercise.id)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Learner, HistoryAnswerQuestion.learner_id == Learner.id)
        .where(HistoryAnswerQuestion.learner_id == learner_id)
        .where(Lesson.id == lesson_id)
    )
    data = session.exec(statement).all()
    return data


def get_history_by_learner(session: Session, learner_id: int):
    statement = (
        select(
            HistoryAnswerQuestion.id,
            HistoryAnswerQuestion.timesecond,
            Question.answer,
            HistoryAnswerQuestion.user_answer,
            Question.difficulty,
            Question.question,
            Question.correct_answer,
        )
        .join(Question, HistoryAnswerQuestion.question_id == Question.id)
        .join(Exercise, Question.exercise_id == Exercise.id)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Learner, HistoryAnswerQuestion.learner_id == Learner.id)
        .where(HistoryAnswerQuestion.learner_id == learner_id)
    )
    data = session.exec(statement).all()
    return data


def get_filtered_history(
    session: Session,
    learner_id: int,
    *,
    lesson_id: int | None = None,
    topic_id: int | None = None,
    since_days: int | None = None,
    limit: int = 20,
):
    """Lấy history kèm thông tin question/lesson/topic, có filter linh hoạt.

    Returns rows with mapping:
      history_id, question_id, user_answer, timesecond,
      question, correct_answer, q_type, difficulty,
      lesson_id, lesson_name, topic_id, topic_name
    """
    statement = (
        select(
            HistoryAnswerQuestion.id.label("history_id"),
            HistoryAnswerQuestion.question_id,
            HistoryAnswerQuestion.user_answer,
            HistoryAnswerQuestion.timesecond,
            Question.question,
            Question.correct_answer,
            Question.type.label("q_type"),
            Question.difficulty,
            Lesson.id.label("lesson_id"),
            Lesson.name.label("lesson_name"),
            Topic.id.label("topic_id"),
            Topic.name.label("topic_name"),
        )
        .join(Question, HistoryAnswerQuestion.question_id == Question.id)
        .join(Exercise, Question.exercise_id == Exercise.id)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Topic, Lesson.topic_id == Topic.id)
        .where(HistoryAnswerQuestion.learner_id == learner_id)
    )

    if lesson_id is not None:
        statement = statement.where(Lesson.id == lesson_id)
    if topic_id is not None:
        statement = statement.where(Topic.id == topic_id)
    if since_days is not None and since_days > 0:
        since_dt = datetime.now(timezone.utc) - timedelta(days=since_days)
        statement = statement.where(HistoryAnswerQuestion.timesecond >= since_dt)

    statement = statement.order_by(
        HistoryAnswerQuestion.timesecond.desc()
    ).limit(max(1, int(limit or 20)))

    return session.exec(statement).all()



_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _normalize_answer_part(part: str) -> str:
    cleaned = part.strip().lower().translate(_PUNCT_TABLE)
    return " ".join(cleaned.split())


def compare_strings(s1: str, s2: str) -> bool:
    s1 = s1 or ""
    s2 = s2 or ""
    list1 = [p for p in (_normalize_answer_part(x) for x in s1.split(",")) if p]
    list2 = [p for p in (_normalize_answer_part(x) for x in s2.split(",")) if p]
    return list1 == list2


def get_difficulty_and_respone(
    session: Session, lesson_id: int, learner_id: int
):
    items_database = []
    respones_database = []
    history = get_history_by_learner_and_lesson(
        session, lesson_id=lesson_id, learner_id=learner_id
    )
    print(f"history: {history}")
    for i in history:
        items_database.append([1, max(-3, min(i[4], 3))])
        print("Chi tiet cac phan tu")
        print(f"i[2]: {i[2]}, i[3]: {i[3]}")
        respone = compare_strings(i[2], i[3])
        if respone:
            respones_database.append(1)
        else:
            respones_database.append(0)
    print(f"items_database: {items_database}")
    print(f"respones_database: {respones_database}")
    return items_database, respones_database
