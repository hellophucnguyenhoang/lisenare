import numpy as np


def info(arr):
    print(arr)
    print(np.sum(arr))
    print()


a = np.load("assets/embeddings/snippets_mean.npy")
info(a)

a_bytes = a.tobytes()
b = np.frombuffer(a_bytes, dtype=np.float64)

info(b)
print(b.dtype)
