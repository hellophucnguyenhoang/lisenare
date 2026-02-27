from fastapi import APIRouter, UploadFile, HTTPException
from ai_model_server.services.transcription_service import (
    preprocess_upload_file,
    transcription_service, 
    phoneme_recognition_service,
)
from schemas.audio import STTResponse

router = APIRouter(prefix="/audio", tags=["Audio Features"])

@router.post("/transcripts", response_model=STTResponse)
async def transcribe_audio(file: UploadFile):
    audio_data = await preprocess_upload_file(file)
    transcript = await transcription_service.transcribe(audio_data)
    return STTResponse(transcript=transcript)

@router.post("/phonemes", response_model=STTResponse)
async def get_phonemes(file: UploadFile):
    try:
        audio_data = await preprocess_upload_file(file)
        phoneme_str = await phoneme_recognition_service.get_phonemes_from_array(audio_data)
        return STTResponse(transcript=phoneme_str)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Phoneme recognition failed: {str(e)}")
    finally:
        await file.close()
