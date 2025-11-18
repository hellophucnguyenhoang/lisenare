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

    # Get cleaned transcript
    transcript = ytb_preprocess.get_clean_transcript(video_id)

    # Insert transcript segments
    for seg in transcript:
        c.execute(
            "INSERT INTO subtitles (video_id, text, start) VALUES (?, ?, ?)",
            (video_id, seg['text'], seg['start'])
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
    c.execute("SELECT video_id, text, start FROM subtitles WHERE subtitles MATCH ?", (q,))
    results = c.fetchall()
    
    response = []
    for video_id, text, start in results:
        c.execute("SELECT url FROM videos WHERE id=?", (video_id,))
        video_info = c.fetchone()
        video_url = f"{video_info[0]}&t={int(start)}s"
        response.append({
            "url": video_url,
            "text": text,
            "start": start
        })
    return response
