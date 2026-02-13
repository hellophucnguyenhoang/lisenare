from fastapi import APIRouter
from schemas.sentence import (
    SentenceCompareRequest, 
    SentenceCompareResponse
)
import app.http_client as http_client

router = APIRouter(prefix="/text", tags=["Text Features"])

@router.post("/comparisons", response_model=SentenceCompareResponse)
async def compare(sentence_compare_req: SentenceCompareRequest):
    r = await http_client.client.post(
        "/text/comparisons",
        json=sentence_compare_req.model_dump(),
    )
    sentence_compare_res = SentenceCompareResponse.model_validate(r.json())
    return sentence_compare_res
