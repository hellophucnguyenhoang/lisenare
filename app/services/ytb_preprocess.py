import re
from youtube_transcript_api import YouTubeTranscriptApi
ytt_api = YouTubeTranscriptApi()
import yt_dlp

def get_raw_transcripts(video_id):
    fetched_transcript = ytt_api.fetch(video_id)
    raw_transcript = fetched_transcript.to_raw_data()
    return raw_transcript


def get_video_ids(channel_url="https://www.youtube.com/@mrmememe777/videos"):

    ydl_opts = {
        'extract_flat': True,   # don't download video, just metadata
        'skip_download': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        # info['entries'] is a list of videos
        video_ids = [entry['id'] for entry in info['entries'] if 'id' in entry]

    return video_ids


def split_sentences(segment):
    """
    Split a text into multiple segments at sentence boundaries.
    Keeps the same start time for all pieces.
    """
    text = segment['text'].strip()
    start = segment['start']
    
    # Split after punctuation followed by space or end of string
    parts = re.split(r'(?<=[.!?])\s+', text)
    
    return [{'text': p, 'start': start} for p in parts if p]


def merge_incomplete_segments(segments):
    SENTENCE_END_RE = re.compile(r'[.!?]$')  # segment ends with ., !, or ?
    """
    Merge segments that don't end with sentence punctuation with the next one.
    Keeps the earliest start time.
    """
    merged = []
    buffer_text = ""
    buffer_start = None
    
    for seg in segments:
        text = seg['text']
        start = seg['start']
        
        if buffer_text == "":
            buffer_text = text
            buffer_start = start
        else:
            buffer_text += " " + text
        
        # If ends with sentence punctuation, commit buffer
        if SENTENCE_END_RE.search(buffer_text):
            merged.append({'text': buffer_text.strip(), 'start': buffer_start})
            buffer_text = ""
            buffer_start = None
    
    # Add any leftover text
    if buffer_text:
        merged.append({'text': buffer_text.strip(), 'start': buffer_start})
    
    return merged


def clean_transcripts(raw_transcript):
    # Step 1: split sentences
    split_segments = []
    for seg in raw_transcript:
        split_segments.extend(split_sentences(seg))

    # Step 2: merge incomplete segments
    simplified = merge_incomplete_segments(split_segments)
    return simplified


def get_clean_transcript(video_id):
    raw_transcript = get_raw_transcripts(video_id)
    transcripts = clean_transcripts(raw_transcript)
    return transcripts

if __name__ == "__main__":
    video_ids = get_video_ids()
    
