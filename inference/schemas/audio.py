from sqlmodel import SQLModel


class WordSegment(SQLModel):
    word: str
    start_frame: int
    end_frame: int
    score: float

    @property
    def duration_frames(self) -> int:
        return self.end_frame - self.start_frame

    def to_seconds(self, frames_per_second: float) -> tuple[float, float]:
        """Convert frame indices to seconds (start, end)"""
        start_sec = self.start_frame / frames_per_second
        end_sec = self.end_frame / frames_per_second
        return start_sec, end_sec


class AlignmentRequest(SQLModel):
    audio_url: str
    transcript: str


class WordSegmentResponse(SQLModel):
    word: str
    start_frame: int
    end_frame: int
    score: float
    start_sec: float
    end_sec: float


class AlignmentResponse(SQLModel):
    segments: list[WordSegmentResponse]
    frames_per_second: float
