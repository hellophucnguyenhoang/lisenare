from sqlmodel import Session, create_engine
from app.services.topics import get_all_topics
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.cluster import KMeans
from collections import defaultdict


engine = create_engine("sqlite:///database.db")

with Session(engine) as session:
    topics = get_all_topics(session)

topic_names = [topic.name for topic in topics]

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
embeddings = model.encode(topic_names, convert_to_numpy=True)

num_clusters = 10
kmeans = KMeans(n_clusters=num_clusters, random_state=42)
labels = kmeans.fit_predict(embeddings)

clusters = defaultdict(list)
for topic_name, label in zip(topic_names, labels):
    clusters[label].append(topic_name)


for label in clusters:
    print(f"Group: {label}")
    print(clusters[label])
    print()

cluster_names = {
    0: "Biography",
    1: "Arts",
    2: "Life",
    3: "History",
    4: "Travel",
    5: "Animals",
    6: "Education",
    7: "Society",
    8: "Sports",
    9: "Environment",
}

topic_to_cluster = {
    # Group 0
    "biography": 0, "personal qualities": 0, "person": 0, "object": 0,

    # Group 1
    "fashion": 1, "literature": 1, "art": 1, "music": 1, "arts": 1,
    "persion": 1, "book": 1, "folktales": 1, "archaeology": 1,

    # Group 2
    "life": 2, "health": 2, "personal experience": 2, "safety": 2,
    "growing up": 2, "survival": 2, "courage": 2, "job": 2,
    "attitude": 2, "friendship": 2, "friend": 2, "home": 2,
    "seasons": 2, "childhood": 2,

    # Group 3
    "history": 3, "social studies": 3, "psychology": 3, "politics": 3,

    # Group 4
    "transportation": 4, "travel": 4, "leisure": 4,
    "transport": 4, "shopping": 4,

    # Group 5
    "wildlife": 5, "animal": 5, "animals": 5, "food": 5, "objects": 5,

    # Group 6
    "education": 6, "business": 6, "personal development": 6,
    "communication": 6, "science": 6, "technology": 6,
    "language": 6, "challenges": 6,

    # Group 7
    "family": 7, "culture": 7, "society": 7, "behavior": 7,
    "behaviour": 7, "tradition": 7, "forgiveness": 7,
    "social gathering": 7, "socializing": 7,

    # Group 8
    "sports": 8, "sport": 8, "fantasy": 8, "entertainment": 8,
    "calls": 8, "school": 8, "hobbies": 8, "celebration": 8,

    # Group 9
    "natural disasters": 9, "nature": 9, "environment": 9,
    "human nature": 9, "resilience": 9, "natural": 9,
}

def clusterize(name: str):
    key = name.lower().strip()
    
    if key not in topic_to_cluster:
        return None, None   # -1, "Uncategorized"
    
    cid = topic_to_cluster[key]
    cname = cluster_names[cid]
    
    return cid, cname
