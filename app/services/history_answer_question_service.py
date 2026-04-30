from app.database import HistoryAnswerQuestion
from sqlmodel import Session

def insert_history_answer_question(session: Session,  historyanswerquestion: HistoryAnswerQuestion):
    try:
        session.add(historyanswerquestion)
        session.commit()
    except Exception as e :
        session.rollback()
        print(f"Lỗi khi thêm lịch sử: {e}")

def insert_list_history_answer_question(session: Session, listhistoryanswerquestion: list[HistoryAnswerQuestion]):
    try:
        for history in listhistoryanswerquestion:
            session.add(history)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Lỗi khi thêm list historyanswerquestion vào database:{e}")


