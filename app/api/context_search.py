from fastapi import APIRouter, Depends
from app.schemas import WritingCheckRequest, WritingCheckResponse
from app.database import get_db
from sqlite3 import Connection
from app.services import ytb_preprocess, context_search

router = APIRouter(prefix="/context-search", tags=["Context Search"])

@router.get("/search")
def search_subtitles(q: str, db: Connection = Depends(get_db)):
    return context_search.search_subtitles_from_db(q=q, db=db)

@router.post("/add")
def add_subtitles(video_id: str, db: Connection = Depends(get_db)):
    return context_search.add_subtitles_to_db(video_id=video_id, db=db)
