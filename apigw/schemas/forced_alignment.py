from schemas.base import Schema


class WordSegmentSecond(Schema):
    word: str
    start_sec: float
    end_sec: float
