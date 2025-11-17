from fastapi import APIRouter
from app.schemas import WritingCheckRequest, WritingCheckResponse
from app.services import coedit

router = APIRouter(prefix="/coedit", tags=["CoEdIT"])

@router.post("/edit", response_model=WritingCheckResponse)
def coedit_api(req: WritingCheckRequest):
    # Split text into sentences
    final, sentence_count = coedit.run_paragraph(req.instruction, req.text)
    return WritingCheckResponse(edited_text=final, total_sentences=sentence_count)
