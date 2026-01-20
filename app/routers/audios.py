from fastapi import APIRouter, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
from app.services.transcription_service import transcription_service
from app.schemas import STTResponse, TTSRequest
from app.services.tts_service import tts_service
import random

router = APIRouter(prefix="/audio", tags=["Audio Features"])

@router.post("/transcribe", response_model=STTResponse)
async def transcribe_audio(file: UploadFile):
    transcript = await transcription_service.transcribe(file)
    return STTResponse(transcript=transcript)

@router.get("/synthesize")
def synthesize_text_stream(text: str):
    random_number = random.random()
    print(f"start_synthesize:{random_number}")
    return StreamingResponse(
        tts_service.tts_stream(text),
        media_type="audio/wav"
    )

@router.post("/synthesize")
async def synthesize_text(request: TTSRequest):
    file_path = await tts_service.synthesize_to_file(request.text)
    return FileResponse(
        path=file_path, 
        media_type="audio/wav", 
        filename="speech.wav"
    )
