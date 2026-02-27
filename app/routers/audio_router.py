from fastapi import APIRouter, UploadFile, Depends
from sqlmodel import Session
from schemas.audio import STTResponse
import app.http_client as http_client
from app.database import get_session
from app.schemas import PronunciationAnalysisResponse
from app.services.text_service import text_service
from app.services import brick_service
from phonemizer import phonemize
from phonemizer.separator import Separator

router = APIRouter(prefix="/audio", tags=["Audio"])

@router.post("/transcripts", response_model=STTResponse)
async def transcribe_audio(file: UploadFile):
    files = {
        "file": (
            file.filename,
            await file.read(),
            file.content_type,
        )
    }
    r = await http_client.client.post("/audio/transcripts", files=files)
    return r.json()

@router.post("/phonemes", response_model=STTResponse)
async def get_phonemes(file: UploadFile):
    files = {
        "file": (
            file.filename,
            await file.read(),
            file.content_type,
        )
    }
    r = await http_client.client.post("/audio/phonemes", files=files)
    return r.json()

@router.post("/ipa-evaluation", response_model=PronunciationAnalysisResponse)
async def evaluate_audio(
    target_brick_id: int, 
    learner_file: UploadFile, 
    session: Session = Depends(get_session)
):
    """
    About this approach:\n
    Good: short words, very precise when we know the transcript because we don't have noise.\n
    Bad: sentences, the sound still might be understandable to got a right transcript but the pronunciation is not right.
    """
    target_brick = brick_service.get_brick(session, target_brick_id)
    sep = Separator(phone=' ', word='  ')
    teacher_ipa = phonemize(target_brick.target_text, separator=sep)

    learner_files = {
        "file": (
            learner_file.filename,
            await learner_file.read(),
            learner_file.content_type,
        )
    }
    learner_result = await http_client.client.post("/audio/transcripts", files=learner_files)
    learner_ipa = phonemize(learner_result.json()["transcript"], separator=sep)
    print(f"learner_transcript:{learner_result.json()["transcript"]}")
    print(f"teacher_ipa:{teacher_ipa}")
    print(f"learner_ipa:{learner_ipa}")
    result = text_service.evaluate_ipa_pronunciation(
        teacher_ipa=teacher_ipa, 
        learner_ipa=learner_ipa
    )
    return result
