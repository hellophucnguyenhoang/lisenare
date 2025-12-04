# kmeans_elbow.py
from sqlmodel import Session, create_engine
from app.services.item_embeddings import get_all_embeddings
from app.services.readings import get_full_reading_by_id
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
plt.title('Phương pháp Elbow (KMeans) cho embedding các bài học')
plt.grid(True)
plt.savefig("elbow_plot.png")
print("✅ Saved: elbow_plot.png")

best_k = 3
km = KMeans(n_clusters=best_k, random_state=42)
labels = km.fit_predict(X)

# Gộp ID theo cụm
clusters = {}
for cluster_id in range(best_k):
    clusters[cluster_id] = [item_ids[i] for i, label in enumerate(labels) if label == cluster_id]

# In kết quả + tính % độ khó
for cluster_id, ids in clusters.items():
    print(f"\n🔹 Cụm {cluster_id} ({len(ids)} items):")
    print(ids)

    # Đếm độ khó
    diff_count = {d: 0 for d in range(6)}  # 0..5
    for rid in ids:
        reading = get_full_reading_by_id(session, rid)
        diff_count[reading.difficulty] += 1

    # Tính % cho từng độ khó
    print("   ▪️ Phân bố độ khó:")
    total = len(ids)
    for d in range(6):
        pct = diff_count[d] * 100 / total if total > 0 else 0
        print(f"      - Level {d}: {pct:.2f}% ({diff_count[d]} items)")

