from pydantic import BaseModel


class STTResponse(BaseModel):
    transcript: str
