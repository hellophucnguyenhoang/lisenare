from fastapi import APIRouter, HTTPException, UploadFile, status

from ai_model_server.services.transcription_service import (
    phoneme_recognition_service,
    preprocess_upload_file,
    transcription_service,
)
from schemas.audio import STTResponse

router = APIRouter(prefix="/audio", tags=["Audio Features"])


@router.post("/transcripts")
async def transcribe_audio(file: UploadFile) -> STTResponse:
    audio_data = await preprocess_upload_file(file)
    transcript = await transcription_service.transcribe(audio_data)
    return STTResponse(transcript=transcript)


@router.post("/phonemes")
async def get_phonemes(file: UploadFile) -> STTResponse:
    try:
        audio_data = await preprocess_upload_file(file)
        phoneme_str = (
            await phoneme_recognition_service.get_phonemes_from_array(
                audio_data
            )
        )
        return STTResponse(transcript=phoneme_str)
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Phoneme recognition failed: {str(e)}",
        )
    finally:
        await file.close()
