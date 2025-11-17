from fastapi import APIRouter
from app.schemas import CEFRClassificationRequest, CEFRClassificationResponse
from app.services import readmepp

router = APIRouter(prefix="/readmepp", tags=["ReadMe++"])

@router.post("/classify")
def coedit_api(req: CEFRClassificationRequest):
    # Split text into sentences
    cefr_index = readmepp.predict_cefr(req.text)
    cefr_label = readmepp.INDEX2CEFR[cefr_index]
    return CEFRClassificationResponse(cefr_index=cefr_index, cefr_label=cefr_label)
