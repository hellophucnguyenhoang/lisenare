from fastapi import APIRouter, HTTPException, Depends
from app.schemas import RecommendRequest, RecommendResponse
from app.services.generate_question import generate_question_from_passage, find_user_by_user_name
from sqlmodel import Session
from app.database import get_session
from app.services.finduser import find_reading_question, find_reading_by_user_id, format_reading_data
import time
from app.services import users as user_service

router = APIRouter(prefix="/finduser", tags=["Question Recommendation"])

@router.get("/user")
def find_user(username: str, session: Session = Depends(get_session)):
    try:
        user_id = user_service.get_id_by_username(session, username)
        reading_list = find_reading_by_user_id(user_id)
        print(reading_list)
        reading_list_id = [reading[0][0] for reading in reading_list]
        result = find_reading_question(reading_list_id)
        clean_results = format_reading_data(result)
        return clean_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
