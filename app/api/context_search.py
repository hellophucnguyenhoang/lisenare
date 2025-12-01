from fastapi import APIRouter, Depends
from app.schemas import ContextSearchRequest, ContextSearchResponse, ContextSearchResult
from app.database import get_db
from sqlite3 import Connection
from app.services import context_search
import chromadb
from app.config import settings
import json

router = APIRouter(prefix="/context-search", tags=["Context Search"])


# Load ChromaDB once at startup (faster)
chroma_client = chromadb.PersistentClient(settings.chroma_subtitles_url)
collection = chroma_client.get_collection("subtitles")


@router.post("/search", response_model=ContextSearchResponse)
def search_subtitles(req: ContextSearchRequest, db: Connection = Depends(get_db)):
    literal_results = context_search.search_literal_subtitles(req.query, db)
    print('search_literal_subtitles')
    semantic_results = context_search.search_semantic_subtitles(req.query, req.n_results, collection)
    print('search_semantic_subtitles')
    return context_search.remove_duplicates(literal_results + semantic_results)
    

@router.post("/add")
def add_subtitles(video_id: str, db: Connection = Depends(get_db)):
    return context_search.add_subtitles_to_db(video_id=video_id, db=db)
