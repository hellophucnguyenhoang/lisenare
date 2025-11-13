# pca_optimal_dim_ratio.py
from sqlmodel import Session, create_engine
from app.services.item_embeddings import get_all_item_embeddings
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

# --- Load dữ liệu ---
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, _ = get_all_item_embeddings(session)

X = np.array(reading_embeddings)
n_total_dims = X.shape[1]
print("Shape:", X.shape)

# --- PCA ---
pca = PCA().fit(X)
explained = np.cumsum(pca.explained_variance_ratio_)  # a
dims = np.arange(1, len(explained) + 1)
b = dims / n_total_dims  # tỉ lệ số chiều (so với tối đa)
score = explained / b     # tỉ lệ hiệu quả a/b

# --- Tìm điểm tối ưu ---
best_idx = np.argmax(score)
best_dim = dims[best_idx]
best_score = score[best_idx]
best_a = explained[best_idx]
best_b = b[best_idx]

print(f"🌟 Số chiều tối ưu: {best_dim}")
print(f"   Giữ lại {best_a*100:.2f}% thông tin, "
      f"sử dụng {best_b*100:.2f}% số chiều "
      f"→ tỉ lệ a/b = {best_score:.2f}")

# --- Vẽ biểu đồ ---
plt.figure()
plt.plot(dims, explained, label='Thông tin giữ lại (a)')
plt.plot(dims, b, label='Tỉ lệ số chiều (b)')
plt.plot(dims, score / np.max(score), label='Hiệu quả (a/b, chuẩn hóa)')
plt.axvline(best_dim, color='red', linestyle='--',
            label=f'Chiều tối ưu = {best_dim}')
plt.xlabel('Số chiều PCA')
plt.ylabel('Tỷ lệ (chuẩn hóa)')
plt.title('Chọn số chiều tối ưu bằng tỉ lệ a/b')
plt.legend()
plt.grid(True)
plt.savefig("pca_ratio_optimal.png")

print("✅ Saved: pca_ratio_optimal.png")
