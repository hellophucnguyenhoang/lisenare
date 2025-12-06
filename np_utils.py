import numpy as np


def blob_to_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

def cosine_sim_batch(a_rows: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Normalize embeddings for cosine similarity
    a_rows_norms = a_rows / np.linalg.norm(a_rows, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b)

    # Cosine similarity
    return a_rows_norms @ b_norm  # shape: (#rows,)

def top_k_nearest_idx(a_rows: np.ndarray, b: np.ndarray, k: int | None = None) -> np.ndarray:
    sims = cosine_sim_batch(a_rows, b)
    sorted_idxs = np.argsort(-sims)
    return sorted_idxs[:k] if k else sorted_idxs

def top_k_l2_nearest_idx(db: np.ndarray, query: np.ndarray, k=1):
    dists = np.linalg.norm(db - query, axis=1)
    return np.argsort(dists)[:k]