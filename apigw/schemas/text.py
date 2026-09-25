from fastapi.responses import StreamingResponse
from sqlmodel import Field, SQLModel


class WAVStreamingResponse(StreamingResponse):
    media_type = "audio/wav"


class PhonemeStatus(SQLModel):
    phoneme: str
    status: str


class PronunciationAnalysisResponse(SQLModel):
    accuracy_score: float = Field(ge=0, le=1)
    analysis: list[PhonemeStatus]
    learner_phonemes: list[str]
