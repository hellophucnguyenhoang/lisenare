# kmeans_elbow.py
from sqlmodel import Session, create_engine
from app.services.item_embeddings import get_all_embeddings
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from app.config import settings

# --- Load dữ liệu ---
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, item_ids = get_all_embeddings(session)

X = np.array(reading_embeddings)
print("Shape:", X.shape)

# --- Elbow method ---
inertias = []
K = range(2, 10)
for k in K:
    km = KMeans(n_clusters=k, random_state=42)
    km.fit(X)
    inertias.append(km.inertia_)

plt.figure()
plt.plot(K, inertias, marker='o')
plt.xlabel('Số cụm (k)')
plt.ylabel('Inertia')
plt.title('Phương pháp Elbow (KMeans)')
plt.grid(True)
plt.savefig("elbow_plot.png")
print("✅ Saved: elbow_plot.png")

best_k = 4
km = KMeans(n_clusters=best_k, random_state=42)
labels = km.fit_predict(X)

# Gộp ID theo cụm
clusters = {}
for cluster_id in range(best_k):
    clusters[cluster_id] = [item_ids[i] for i, label in enumerate(labels) if label == cluster_id]

# In kết quả
for cluster_id, ids in clusters.items():
    print(f"\n🔹 Cụm {cluster_id} ({len(ids)} items):")
    print(ids)
