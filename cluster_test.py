from reading_rec_env import ReadingRecEnvContinuous
import numpy as np
from app.services.item_embeddings import get_all_item_embeddings
from sqlmodel import Session, create_engine


engine = create_engine("sqlite:///database.db")

with Session(engine) as session:
    reading_embeddings, _ = get_all_item_embeddings(session)


X = np.array(reading_embeddings)
print(X.shape)  # (num_items, 392)

from sklearn.decomposition import PCA

pca = PCA(n_components=10)  # hoặc 2 để visualize
X_reduced = pca.fit_transform(X)
explained_variance = np.cumsum(pca.explained_variance_ratio_)
print(explained_variance[-1])  # tổng phương sai giữ lại với 50 chiều

from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

inertias = []
K = range(2, 10)
for k in K:
    km = KMeans(n_clusters=k, random_state=42)
    km.fit(X_reduced)
    inertias.append(km.inertia_)

plt.plot(K, inertias, marker='o')
plt.xlabel('Số cụm (k)')
plt.ylabel('Inertia')
plt.title('Phương pháp Elbow')
plt.savefig("figure.png")  # lưu ra file


# Giảm xuống 2 chiều để visualize
pca_2d = PCA(n_components=2)
X_2d = pca_2d.fit_transform(X)

# Fit lại KMeans với k=3
km = KMeans(n_clusters=3, random_state=42)
labels = km.fit_predict(X_2d)

# Vẽ cụm
plt.figure(figsize=(6,6))
plt.scatter(X_2d[:, 0], X_2d[:, 1], c=labels, cmap='viridis', s=30)
plt.scatter(km.cluster_centers_[:, 0], km.cluster_centers_[:, 1],
            c='red', marker='x', s=100, label='Tâm cụm')
plt.title('KMeans với k=3 sau khi giảm PCA về 2D')
plt.legend()
plt.savefig("clusters_visualization.png")