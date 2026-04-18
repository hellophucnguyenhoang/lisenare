import re

import torch
import torchaudio
from sqlmodel import Session, SQLModel

from app.schemas import WordSegmentSecond

from . import snippet_service

# --------------------- Global Model ---------------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

BUNDLE = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
MODEL = BUNDLE.get_model().to(DEVICE)
LABELS = BUNDLE.get_labels()
DICTIONARY = {c: i for i, c in enumerate(LABELS)}
SAMPLE_RATE = BUNDLE.sample_rate
BLANK_ID = DICTIONARY["-"]


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


# --------------------- Core Functions ---------------------
def get_emission(audio_path: str):
    """Load audio, resample if needed, and get log-softmax emissions."""
    with torch.inference_mode():
        waveform, sample_rate = torchaudio.load(audio_path)
        if sample_rate != SAMPLE_RATE:
            waveform = torchaudio.functional.resample(
                waveform, sample_rate, SAMPLE_RATE
            )
        emissions, _ = MODEL(waveform.to(DEVICE))
        emissions = torch.log_softmax(emissions, dim=-1)

    return (
        emissions[0].cpu().detach(),
        waveform.shape[1],
        len(emissions[0]),
    )


def get_trellis(emission: torch.Tensor, tokens: list[int], blank_id: int = 0):
    """Build the trellis for forced alignment."""
    num_frame, num_tokens = emission.size(0), len(tokens)
    trellis = torch.zeros((num_frame, num_tokens))

    trellis[1:, 0] = torch.cumsum(emission[1:, blank_id], 0)
    trellis[0, 1:] = float("-inf")
    trellis[-num_tokens + 1 :, 0] = float("inf")

    for t in range(num_frame - 1):
        trellis[t + 1, 1:] = torch.maximum(
            trellis[t, 1:] + emission[t, blank_id],  # stay token score
            trellis[t, :-1] + emission[t, tokens[1:]],  # change score
        )
    return trellis


class Point:
    """Helper for backtracking path."""

    def __init__(self, token_index: int, time_index: int, score: float):
        self.token_index = token_index
        self.time_index = time_index
        self.score = score


def backtrack(
    trellis: torch.Tensor,
    emission: torch.Tensor,
    tokens: list[int],
    blank_id: int = 0,
):
    """Backtrack to find the best alignment path."""
    t, j = trellis.size(0) - 1, trellis.size(1) - 1
    path = [Point(j, t, emission[t, blank_id].exp().item())]

    while j > 0:
        assert t > 0
        p_stay = emission[t - 1, blank_id]
        p_change = emission[t - 1, tokens[j]]

        stayed = trellis[t - 1, j] + p_stay
        changed = trellis[t - 1, j - 1] + p_change

        t -= 1
        if changed > stayed:
            j -= 1
        prob = (p_change if changed > stayed else p_stay).exp().item()
        path.append(Point(j, t, prob))

    # Fill remaining frames with blank
    while t > 0:
        prob = emission[t - 1, blank_id].exp().item()
        path.append(Point(j, t - 1, prob))
        t -= 1

    return path[::-1]


def merge_repeats(path: list[Point], transcript: str):
    """Merge consecutive repeats of the same token into segments."""
    segments = []
    i1 = i2 = 0
    while i1 < len(path):
        while i2 < len(path) and path[i1].token_index == path[i2].token_index:
            i2 += 1
        score = sum(p.score for p in path[i1:i2]) / (i2 - i1)
        segments.append(
            {
                "label": transcript[path[i1].token_index],
                "start": path[i1].time_index,
                "end": path[i2 - 1].time_index + 1,
                "score": score,
            }
        )
        i1 = i2
    return segments


def merge_words(segments: list[dict], separator: str = "|"):
    """Group character segments into words."""
    words = []
    i1 = i2 = 0
    while i1 < len(segments):
        if i2 >= len(segments) or segments[i2]["label"] == separator:
            if i1 != i2:
                segs = segments[i1:i2]
                word = "".join(s["label"] for s in segs)
                total_length = sum(s["end"] - s["start"] for s in segs)
                score = (
                    sum(s["score"] * (s["end"] - s["start"]) for s in segs)
                    / total_length
                )
                words.append(
                    WordSegment(
                        word=word,
                        start_frame=segments[i1]["start"],
                        end_frame=segments[i2 - 1]["end"],
                        score=score,
                    )
                )
            i1 = i2 + 1
            i2 = i1
        else:
            i2 += 1
    return words


def normalize_transcript(text: str) -> str:
    words = re.findall(r"[a-zA-Z']+", text)
    return "|" + "|".join(w.upper() for w in words) + "|"


# --------------------- Main API ---------------------
def align_audio_to_transcript(
    audio_path: str,
    transcript: str,
) -> list[WordSegment]:
    """
    Align audio with given transcript and return word-level segments with frame timestamps.
    """
    emission, num_samples, num_frames = get_emission(audio_path)

    # Prepare tokens (include | as word separator)
    tokens = [DICTIONARY[c] for c in transcript]

    trellis = get_trellis(emission, tokens)
    path = backtrack(trellis, emission, tokens)

    char_segments = merge_repeats(path, transcript)
    word_segments = merge_words(char_segments)

    return word_segments, num_frames / (num_samples / SAMPLE_RATE)


def align(session: Session, audio_path: str) -> list[WordSegmentSecond]:
    snippet = snippet_service.get_snippet_by_audio_path(session, audio_path)
    transcript = normalize_transcript(snippet.content)
    words, frames_per_sec = align_audio_to_transcript(audio_path, transcript)

    return [
        WordSegmentSecond(
            word=w.word,
            start_sec=w.start_frame / frames_per_sec,
            end_sec=w.end_frame / frames_per_sec,
        )
        for w in words
    ]


# --------------------- Example Usage ---------------------
if __name__ == "__main__":
    audio_file = "she_ran_out.wav"
    transcript = "She ran out of the room, slamming the door behind her."

    transcript = normalize_transcript(transcript)
    words, frames_per_sec = align_audio_to_transcript(audio_file, transcript)

    print("Word\tStart (s)\tEnd (s)")
    for w in words:
        start_s, end_s = w.to_seconds(frames_per_sec)
        print(f"{w.word[:6]}\t{start_s:.3f}\t{end_s:.3f}")
