from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.services.history_generate_question import get_reading_question_history_by_user_id, group_history_output
from app.services.generate_question import find_user_by_user_name
router = APIRouter(prefix="/history", tags=["History"])


@router.get("/questions/{user_name}")
def get_user_history(user_name: str, session: Session = Depends(get_session)):
    try:
        user_info = find_user_by_user_name(user_name)
        user_id = user_info[0][3]
        results = get_reading_question_history_by_user_id(user_id)
        grouped_output = group_history_output(results)
        return {"message": "success", "data": grouped_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
