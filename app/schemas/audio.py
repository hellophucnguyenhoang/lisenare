from sqlmodel import SQLModel

class AudioTranscription(SQLModel):
    transcript: str
