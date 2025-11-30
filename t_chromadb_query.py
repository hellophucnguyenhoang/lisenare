import chromadb
from app.config import settings

chroma_client = chromadb.PersistentClient(settings.chroma_subtitles_url2)
print(chroma_client.list_collections())
collection = chroma_client.get_collection(name="subtitles")

results = collection.query(
    query_texts=["jump off"],
)

import json 
print(json.dumps(results, indent=2))
