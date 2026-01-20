from sqlmodel import SQLModel

class STTResponse(SQLModel):
    transcript: str

class TTSRequest(SQLModel):
    text: str
