import numpy as np

def softmax(x: np.ndarray):
    probs = np.exp(x - np.max(x))
    probs /= np.sum(probs)
    print(probs)

rarity = np.array([0.2, 1.0, 2.0, 1.2, 0.5])
sensitivity = np.array([-2.0, -1.0, 0.0, 1.5, 1.0])
dense_reward = -1
softmax(rarity + dense_reward * sensitivity)
