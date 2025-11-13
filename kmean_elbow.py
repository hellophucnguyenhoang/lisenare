# kmeans_elbow.py
from sqlmodel import Session, create_engine
from app.services.item_embeddings import get_reduced_item_embeddings
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

# --- Load dữ liệu ---
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, _, _ = get_reduced_item_embeddings(session)

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
