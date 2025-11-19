import sqlite3
from app.config import settings
from collections import defaultdict
from app.services import ytb_preprocess

conn = sqlite3.connect(settings.ytb_subtitles_db_url)
c = conn.cursor()

# Create tables
c.execute("""
CREATE VIRTUAL TABLE IF NOT EXISTS clean_subtitles USING fts5(
    video_id,
    text,
    start,
    duration
)
""")

c.execute("SELECT video_id, text, start, duration FROM subtitles")
raw_transcripts = c.fetchall()

# Group by video_id
video_transcripts = defaultdict(list)
for video_id, text, start, duration in raw_transcripts:
    video_transcripts[video_id].append({
        "text": text,
        "start": float(start),
        "duration": float(duration)
    })


# sort each video’s chunks by start time
for video_id in video_transcripts:
    video_transcripts[video_id].sort(key=lambda x: x["start"])
    processed_chunks = ytb_preprocess.create_hybrid_searchable_segments(video_transcripts[video_id])

    for chunk in processed_chunks:
        c.execute(
            "INSERT INTO clean_subtitles (video_id, text, start, duration) VALUES (?, ?, ?, ?)",
            (video_id, chunk["text"], chunk["start"], chunk["duration"])
        )


conn.commit()
conn.close()

