from fastapi import APIRouter
from app.schemas import WritingCheckRequest, WritingCheckResponse
from app.services import coedit
import time
import logging

logger = logging.getLogger("latency_writing_check")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("latency_writing_check.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

router = APIRouter(prefix="/coedit", tags=["CoEdIT"])

@router.post("/edit", response_model=WritingCheckResponse)
def coedit_api(req: WritingCheckRequest):
    
    start = time.time()
    # Split text into sentences
    final, sentence_count = coedit.run_paragraph(req.instruction, req.text)
    # ---- Tổng độ trễ backend ----
    total_ms = (time.time() - start) * 1000
    logger.info(f"total={total_ms:.2f} ms")

    return WritingCheckResponse(edited_text=final, total_sentences=sentence_count)
