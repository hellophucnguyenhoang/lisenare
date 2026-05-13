from sqlmodel import Session, select

from app.database import (
    Exercise,
    HistoryAnswerQuestion,
    Learner,
    Lesson,
    Question,
)


def insert_history_answer_question(
    session: Session, historyanswerquestion: HistoryAnswerQuestion
):
    try:
        session.add(historyanswerquestion)
        session.commit()
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
    except Exception as e:
        session.rollback()
        print(f"Lỗi khi thêm list historyanswerquestion vào database:{e}")


def get_history_by_learner_and_lesson(
    session: Session, lesson_id: int, learner_id: int
):
    statement = (
        select(
            HistoryAnswerQuestion.id,
            HistoryAnswerQuestion.timesecond,
            Question.answer,
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
        )
        .join(Question, HistoryAnswerQuestion.question_id == Question.id)
        .join(Exercise, Question.exercise_id == Exercise.id)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Learner, HistoryAnswerQuestion.learner_id == Learner.id)
        .where(HistoryAnswerQuestion.learner_id == learner_id)
    )
    data = session.exec(statement).all()
    return data


def compare_strings(s1: str, s2: str) -> bool:
    list1 = [x.strip().lower() for x in s1.split(",")]
    list2 = [x.strip().lower() for x in s2.split(",")]
    return list1 == list2


def get_difficulty_and_respone(
    session: Session, lesson_id: int, learner_id: int
):
    items_database = []
    respones_database = []
    history = get_history_by_learner_and_lesson(
        session, lesson_id=lesson_id, learner_id=learner_id
    )
    for i in history:
        items_database.append([1, i[4]])
        respone = compare_strings(i[2], i[3])
        if respone:
            respones_database.append(1)
        else:
            respones_database.append(0)
    return items_database, respones_database
