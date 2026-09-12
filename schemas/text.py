from fastapi.responses import StreamingResponse
from sqlmodel import Field, SQLModel

from app.config import settings


class WAVStreamingResponse(StreamingResponse):
    media_type = "audio/wav"


class TTSRequest(SQLModel):
    text: str = Field(
        default="How are you?",
        max_length=settings.brick_max_words * settings.brick_avg_word_len,
        description=f"Maximum {settings.brick_max_words * settings.brick_avg_word_len} characters",
    )
    voice: str = Field(
        default="af_heart",
        description="Kokoro voice: 'af_heart' / 'am_adam' (English), 'jf_alpha' / 'jm_kumo' (Japanese)",
    )
