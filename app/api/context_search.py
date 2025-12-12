from fastapi import APIRouter, Depends
from app.schemas import ContextSearchRequest, ContextSearchResponse, ContextSearchResult
from app.database import get_db
from sqlite3 import Connection
from app.services import context_search
import chromadb
from app.config import settings
import time
import logging

logger = logging.getLogger("latency_context_search")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("latency_context_search.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

router = APIRouter(prefix="/context-search", tags=["Context Search"])


# Load ChromaDB once at startup (faster)
chroma_client = chromadb.PersistentClient(settings.chroma_subtitles_url2)
collection = chroma_client.get_or_create_collection("subtitles")


@router.post("/search", response_model=ContextSearchResponse)
def search_subtitles(req: ContextSearchRequest, db: Connection = Depends(get_db)):
    start = time.time()
    literal_results = context_search.search_literal_subtitles(req.query, db)
    print('search_literal_subtitles')
    semantic_results = context_search.search_semantic_subtitles(req.query, req.n_results, collection)
    print('search_semantic_subtitles')
    no_duplicate_result = context_search.remove_duplicates(literal_results + semantic_results)
    # ---- Tổng độ trễ backend ----
    total_ms = (time.time() - start) * 1000

    logger.info(f"total={total_ms:.2f} ms")
    return no_duplicate_result
    

@router.post("/add")
def add_subtitles(video_id: str, db: Connection = Depends(get_db)):
    return context_search.add_subtitles_to_db(video_id=video_id, db=db)
