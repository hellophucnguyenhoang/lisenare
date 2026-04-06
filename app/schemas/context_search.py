from sqlmodel import SQLModel


class ContextSearchRequest(SQLModel):
    query: str = "jump off"


class VideoContextSearchResult(SQLModel):
    ytb_video_id: str
    text: str
    start: float
    duration: float
