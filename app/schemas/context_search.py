from sqlmodel import SQLModel


class ContextSearchRequest(SQLModel):
    query: str = "hang out"


class VideoContextSearchResult(SQLModel):
    ytb_video_id: str
    start: float
    duration: float
    transcript: str
