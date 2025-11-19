from sqlite3 import Connection
from . import ytb_preprocess  # adjust import according to your project

def add_subtitles_to_db(video_id: str, db: Connection) -> dict:
    """
    Service function to add a video's subtitles to the database.

    Args:
        video_id (str): YouTube video ID
        db (Connection): SQLite connection

    Returns:
        dict: Information about the inserted video and subtitles
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    c = db.cursor()

    # Insert video (ignore if it already exists)
    c.execute(
        "INSERT OR IGNORE INTO videos (id, url) VALUES (?, ?)",
        (video_id, video_url)
    )

    # If insert was ignored (duplicate), rowcount == 0
    if c.rowcount == 0:
        return {
            "video_id": video_id,
            "message": "Video already exists. Skipping."
        }

    transcript = ytb_preprocess.get_raw_transcripts(video_id)

    # Insert transcript segments
    for seg in transcript:
        c.execute(
            "INSERT INTO subtitles (video_id, text, start, duration) VALUES (?, ?, ?, ?)",
            (video_id, seg['text'], seg['start'], seg['duration'])
        )

    # Commit changes
    db.commit()

    return {
        "video_id": video_id,
        "video_url": video_url,
        "num_segments": len(transcript),
        "message": "Subtitles added successfully"
    }

def search_subtitles_from_db(q: str, db: Connection):
    c = db.cursor()

    # In case:
    # SELECT *
    # FROM clean_subtitles
    # WHERE clean_subtitles MATCH '"I don''t know"'
    q = q.replace("'", "''")
    match_query = f'"{q}"'  # Wrap inside double quotes for phrase search


    # 1. Query FTS5
    c.execute("SELECT video_id, text, start, duration FROM clean_subtitles WHERE clean_subtitles MATCH ?", (match_query,))
    results = c.fetchall()
    
    # 2. Sort results by video_id and start time
    results.sort(key=lambda x: (x[0], x[2]))  # sort by video_id, then start
    
    filtered = []
    last_start_per_video = {}  # track last end time per video for overlap check
    
    for video_id, text, start, duration in results:
        end = start + duration
        
        # Skip if overlapping previous subtitle for same video
        last_end = last_start_per_video.get(video_id, -1)
        if start < last_end:
            continue
        
        # Otherwise, keep it
        last_start_per_video[video_id] = end
        filtered.append((video_id, text, start, duration))
    
    # 3. Build response with video URL
    response = []
    for video_id, text, start, duration in filtered:
        c.execute("SELECT url FROM videos WHERE id=?", (video_id,))
        video_info = c.fetchone()
        video_url = f"{video_info[0]}&t={int(start)}s"
        response.append({
            "url": video_url,
            "text": text,
            "start": start
        })
    
    return response

