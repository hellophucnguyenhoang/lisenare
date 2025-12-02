from fastapi import APIRouter, HTTPException, Depends
from app.schemas import RecommendRequest, RecommendResponse
from app.services.generate_question import generate_question_from_passage
from sqlmodel import Session
from app.database import get_session
router = APIRouter(prefix="/recommendation", tags=["Question Recommendation"])

@router.post("/questions", response_model=RecommendResponse)
def recommend_questions(req: RecommendRequest, session: Session = Depends(get_session)):
    print("===== RECEIVED FROM FE =====")
    print(req.model_dump())  # hoặc print(req.model_dump())
    try:
        result = generate_question_from_passage(req, session)
        print("dinh dang la:", type(result))
        return RecommendResponse(items=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
