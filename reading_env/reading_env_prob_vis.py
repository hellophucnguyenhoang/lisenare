import numpy as np
import matplotlib.pyplot as plt

sensitivity = np.array([-8.0, -5.0, 0.5, 2.0, 1.5])
rarity = np.array([0.5, 2, 2, 1, 0.5])

satisfaction_values = np.linspace(-1, 1, 100)
softmax_probs = []

for s in satisfaction_values:
    logits = rarity + s * sensitivity
    probs = np.exp(logits) / np.sum(np.exp(logits))
    softmax_probs.append(probs)

softmax_probs = np.array(softmax_probs)

actions = ['dislike', 'skip', 'view', 'submit', 'like']

plt.figure(figsize=(10,6))
for i, action in enumerate(actions):
    plt.plot(satisfaction_values, softmax_probs[:, i], label=action)
plt.xlabel('Satisfaction [-1,1]')
plt.ylabel('Probability')
plt.title('Softmax Probabilities vs Satisfaction')
plt.legend()
plt.grid(True)
plt.savefig('probabilities_vs_satisfaction.png')
