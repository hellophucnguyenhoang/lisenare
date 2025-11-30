import chromadb
from chromadb.utils import embedding_functions
import sqlite3
from app.config import settings

BATCH_SIZE = 500

conn = sqlite3.connect(settings.ytb_subtitles_db_url)
c = conn.cursor()

sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-mpnet-base-v2")
chroma_client = chromadb.PersistentClient(settings.chroma_subtitles_url2)
collection = chroma_client.get_or_create_collection(name="subtitles", embedding_function=sentence_transformer_ef)

q = "SELECT * FROM clean_subtitles"
c.execute(q)
subtitles = c.fetchall()
total = len(subtitles)
print(f"[INFO] Loaded {total} rows.")

batch_docs = []
batch_meta = []
batch_ids = []

for i, (video_id, text, start, duration) in enumerate(subtitles, start=1):
    batch_docs.append(text)
    batch_meta.append({
        "video_id": video_id,
        "start": float(start),
        "duration": float(duration),
    })
    batch_ids.append(f"{video_id}_{start}_{duration}")

    if i % BATCH_SIZE == 0:
        collection.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids)
        print(f"[{i}/{total}] inserted...")
        batch_docs, batch_meta, batch_ids = [], [], []

# leftover batch
if batch_docs:
    collection.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids)

print("[DONE] All subtitles inserted.")
