from fastapi.responses import StreamingResponse
from pydantic import Field

from schemas.base import Schema


class WAVStreamingResponse(StreamingResponse):
    media_type = "audio/wav"


class PhonemeStatus(Schema):
    phoneme: str
    status: str


class PronunciationAnalysisResponse(Schema):
    accuracy_score: float = Field(ge=0, le=1)
    analysis: list[PhonemeStatus]
    learner_phonemes: list[str]
