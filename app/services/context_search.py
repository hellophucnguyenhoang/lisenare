from sqlite3 import Connection
from app.schemas import ContextSearchResponse, ContextSearchResult
from . import ytb_preprocess  # adjust import according to your project

# Helper to build YouTube link
def build_youtube_url(video_id: str, start: float) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&t={int(start)}s"

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

def search_literal_subtitles(q: str, db: Connection) -> ContextSearchResponse:
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

        # Skip if 'overlapping' previous subtitle for same video
        last_end = last_start_per_video.get(video_id, -1)
        print(f"start:{start}, last_end:{last_end}")
        if start < last_end + 10:
            continue
        
        # Otherwise, keep it
        end = start + duration
        last_start_per_video[video_id] = end
        filtered.append((video_id, text, start, duration))
    
    # 3. Build response with video URL
    response: list[ContextSearchResult] = []
    for video_id, text, start, duration in filtered:
        c.execute("SELECT url FROM videos WHERE id=?", (video_id,))
        video_info = c.fetchone()
        video_url = f"{video_info[0]}&t={int(start)}s"
        response.append(ContextSearchResult(url=video_url, text=text, start=float(start)))
    return response

def search_semantic_subtitles(query: str, n_results: int, collection) -> ContextSearchResponse:
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    response: list[ContextSearchResult] = []
    for text, meta in zip(documents, metadatas):
        video_id = meta["video_id"]
        start = meta["start"]
        url = build_youtube_url(video_id, start)
        response.append(ContextSearchResult(url=url, text=text, start=float(start)))
    return response

def remove_duplicates(results):
    """
    results: list of (video_id, text, start, duration) OR
             list of ContextSearchResult (having .url, .text, .start and metadata)
    """
    seen = set()
    unique = []
    
    for item in results:
        # Handle both tuple and dataclass/object
        if isinstance(item, tuple):
            video_id = item[0]
            start = item[2]
        else:  # ContextSearchResult or similar object
            # extract video_id & start from metadata encoded in URL
            video_id = item.url.split("v=")[-1].split("&")[0]
            start = int(item.start)
        
        key = (video_id, start)
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique
