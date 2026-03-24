import numpy as np
from numpy.typing import NDArray


def cosine_sim(a: NDArray, b: NDArray) -> np.float64:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
