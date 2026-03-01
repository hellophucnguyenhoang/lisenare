import re
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from typing import Any

ytt_api = YouTubeTranscriptApi()


def get_video_ids(channel_url="https://www.youtube.com/@mrmememe777/videos"):
    ydl_opts = {
        "extract_flat": True,  # don't download video, just metadata
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        # info['entries'] is a list of videos
        video_ids = [entry["id"] for entry in info["entries"] if "id" in entry]
    return video_ids


def get_raw_transcripts(video_id):
    """
    Output:
        chunks = [{text, start, duration}, ...]
    """
    fetched_transcript = ytt_api.fetch(video_id)
    raw_transcript = fetched_transcript.to_raw_data()
    return raw_transcript


# ============================================================
# 1) Convert chunks → flat word list + per-word start time + per-word duration
# ============================================================
def flatten_transcript(chunks: list[dict[str, Any]]):
    """
    Input:
        chunks = [{text, start, duration}, ...]
    Output:
        words = ["hello", "world", ...]
        word_times = [1.23, 1.40, ...]        # per-word start times
        word_durations = [0.12, 0.12, ...]   # per-word durations (evenly split from chunk)
    """
    words: list[str] = []
    word_times: list[float] = []
    word_durations: list[float] = []

    for chunk in chunks:
        text = chunk.get("text", "").strip()
        if not text:
            continue

        start = float(chunk.get("start", 0.0))
        dur = float(chunk.get("duration", 0.0))
        w = text.split()

        if len(w) == 0:
            continue

        # even duration per word (fallback to 0 if chunk duration is 0)
        per_word = dur / len(w) if dur > 0 else 0.0

        for i, word in enumerate(w):
            words.append(word)
            word_times.append(round(start + i * per_word, 2))
            word_durations.append(round(per_word, 2))

    return words, word_times, word_durations


# ============================================================
# 2) Try to find a sentence boundary in a window of text
# ============================================================
def find_sentence_end(words_slice: list[str]):
    """
    Input:  words_slice - list of words (short window)
    Output: number of words up to and including the first word that ends with . ! or ?
            returns None if none of the words end with punctuation
    Purpose: extremely simple rule — avoids regex complexity.
    """
    for i, w in enumerate(words_slice):
        if w.endswith((".", "!", "?")):
            return i + 1
    return None


# -----------------------------
# 3) Make segments (sentence-first, fallback to max_words)
# -----------------------------
def make_segments(
    words: list[str],
    word_times: list[float],
    word_durations: list[float],
    max_words: int,
    overlap: int,
) -> list[dict[str, Any]]:
    """
    Input:
      - words, word_times, word_durations aligned lists
      - max_words: fallback chunk size when no sentence-end found
      - overlap: how many words to overlap between segments
    Output:
      - list of {'text': str, 'start': float, 'duration': float}
    Behavior:
      - Try to end segments at a sentence end within max_words.
      - If no sentence end found or the sentence end is farther than max_words,
        use max_words as fallback (sliding-window behavior).
      - Segment duration is the sum of per-word durations inside the segment.
    """
    n = len(words)
    if n == 0:
        return []

    segments: list[dict[str, Any]] = []
    start_idx = 0
    while start_idx < n:
        # search window
        window_end = min(start_idx + max_words, n)
        window = words[start_idx:window_end]

        found = find_sentence_end(window)
        if found is not None:
            end_idx = start_idx + found
        else:
            # not found → fallback to max_words
            end_idx = min(start_idx + max_words, n)

        seg_words = words[start_idx:end_idx]
        seg_text = " ".join(seg_words)
        seg_start = (
            word_times[start_idx] if start_idx < len(word_times) else 0.0
        )

        # compute duration as sum of per-word durations for words in the segment
        seg_duration = (
            sum(word_durations[start_idx:end_idx])
            if start_idx < len(word_durations)
            else 0.0
        )

        # If seg_duration is zero (e.g., source chunks had zero duration),
        # try a small fallback: approximate by difference between next word start and this start
        if seg_duration == 0.0 and end_idx < len(word_times):
            seg_duration = max(0.0, round(word_times[end_idx] - seg_start, 2))

        segments.append(
            {
                "text": seg_text,
                "start": round(seg_start, 2),
                "duration": round(seg_duration, 2),
            }
        )

        # advance logic: similar to original
        next_i = end_idx - overlap
        if next_i <= start_idx:
            next_i = end_idx  # force forward motion

        # if found a complete sentence, don't do overlap (start next after end)
        if found:
            next_i = end_idx

        start_idx = next_i

    return segments


# -----------------------------
# 4) Public wrapper
# -----------------------------
def create_hybrid_searchable_segments(
    chunks: list[dict[str, Any]], max_words: int = 25, overlap: int = 8
) -> list[dict[str, Any]]:
    """
    Input: raw chunks from YouTubeTranscriptApi, chunks = [{text, start, duration}, ...]
    Output: final searchable segments: [{'text': ..., 'start': ..., 'duration': ...}, ...]
    """
    words, word_times, word_durations = flatten_transcript(chunks)
    return make_segments(
        words, word_times, word_durations, max_words=max_words, overlap=overlap
    )


# ------------------ Example quick test ------------------
if __name__ == "__main__":
    # tiny simulated chunks for quick local test
    sample_chunks = [
        {
            "text": "Hello world. This is a test transcript chunk",
            "start": 0.0,
            "duration": 5.0,
        },
        {
            "text": "It continues here and might have more sentences. Another sentence here!",
            "start": 5.0,
            "duration": 6.0,
        },
        {"text": "Short end", "start": 11.0, "duration": 1.5},
    ]

    segs = create_hybrid_searchable_segments(sample_chunks)
    for s in segs:
        print(f"[{s['start']:>6.2f}s → +{s['duration']:.2f}s] {s['text']}")
