from sqlmodel import SQLModel


class STTResponse(SQLModel):
    transcript: str


class TTSRequest(SQLModel):
    text: str


class TimestampChunk(SQLModel):
    text: str
    timestamp: tuple[float | None, float | None]


class STTTimestampResponse(SQLModel):
    transcript: str
    start_time: float
    end_time: float
    chunks: list[TimestampChunk]
