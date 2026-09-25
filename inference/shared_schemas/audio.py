from sqlmodel import SQLModel


class STTResponse(SQLModel):
    transcript: str
