from sqlmodel import SQLModel

class ContextSearchRequest(SQLModel):
    query: str = "jump off"

class ContextSearchResult(SQLModel):
    ytb_video_id: str
    text: str
    start: float
    duration: float
