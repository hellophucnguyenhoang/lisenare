from fastapi.responses import StreamingResponse
from sqlmodel import SQLModel


class WavStreamingResponse(StreamingResponse):
    media_type = "audio/wav"


class TTSRequest(SQLModel):
    text: str
