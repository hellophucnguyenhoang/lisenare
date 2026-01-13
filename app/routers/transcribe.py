from fastapi import APIRouter, UploadFile
from app.services.transcription_service import transcription_service
from app.schemas import AudioTranscription

router = APIRouter(prefix="/audio", tags=["Audio Features"])

@router.post("/transcribe", response_model=AudioTranscription)
async def transcribe_audio(file: UploadFile):
    transcript = await transcription_service.transcribe(file)
    return AudioTranscription(transcript=transcript)
