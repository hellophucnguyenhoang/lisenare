import numpy as np


a = np.array([3, 4], dtype=np.float32)

a_norm = np.linalg.norm(a)
print(a_norm)