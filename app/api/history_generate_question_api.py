from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.services.history_generate_question import get_reading_question_history_by_user_id, group_history_output
from app.services.generate_question import find_user_by_user_name
router = APIRouter(prefix="/history", tags=["History"])


@router.get("/questions/{user_name}")
def get_user_history(user_name: str, session: Session = Depends(get_session)):
    print(f"--------data nhan tu fe la: {user_name}")
    try:
        user_info = find_user_by_user_name(user_name)
        user_id = user_info[0][3]
        print(f"Truy cap duoc vao thong tin cua nguoi dung:{user_info}")
        results = get_reading_question_history_by_user_id(user_id)
        print(f"history raw thanh cong")
        grouped_output = group_history_output(results)
        print(f"Data gui len be history la:{grouped_output}")
        return grouped_output
    except Exception as e:
        print(f"truy cap history loi")
        raise HTTPException(status_code=500, detail=str(e))
