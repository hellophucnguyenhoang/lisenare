from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.services.question_difficulty_service import (
    recompute_all_due_difficulties,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/recompute-difficulty")
def recompute_difficulty(
    min_responses: int = 20,
    session: Session = Depends(get_session),
):
    """Manual trigger cho job tính lại difficulty của câu hỏi.

    Hữu ích để test hoặc chạy ad-hoc thay vì chờ scheduler 2h sáng.
    """
    stats = recompute_all_due_difficulties(
        session=session, min_responses=min_responses
    )
    return {"status": "ok", "stats": stats}
