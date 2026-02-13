from fastapi import APIRouter, UploadFile
from fastapi.responses import Response
from schemas.audio import STTResponse, TTSRequest
import app.http_client as http_client

router = APIRouter(prefix="/audio", tags=["Audio Features"])

@router.post("/transcribe", response_model=STTResponse)
async def transcribe_audio(file: UploadFile):
    files = {
        "file": (
            file.filename,
            await file.read(),
            file.content_type,
        )
    }
    r = await http_client.client.post("/audio/transcribe", files=files)
    return r.json()
