from sqlmodel import SQLModel


class WordSegmentSecond(SQLModel):
    word: str
    start_sec: float
    end_sec: float
