import torch
from lird_train import Actor, Simulator, evaluate, item_embeddings, historical_data
from app.config import settings

# Hyperparameters must match training
EMBED_DIM = settings.item_embedding_dim  # d = n
N = 5
K = 3

# Instantiate models
actor = Actor(state_dim=EMBED_DIM, action_dim=EMBED_DIM, hidden_dim=EMBED_DIM)
simulator = Simulator(historical_data)

# Load saved weights
checkpoint = torch.load("actor_critic.pth", map_location="cpu")
actor.load_state_dict(checkpoint["actor"])
actor.eval()


# Create random test states (each state = N item embeddings)
NUM_STATES = 500
states = []
for _ in range(NUM_STATES):
    idx = torch.randint(0, item_embeddings.size(0), (N,))
    state = item_embeddings[idx]
    states.append(state)

# Evaluate actor vs random
avg_reward_actor = evaluate(actor, simulator, item_embeddings, states, K)
avg_reward_random = evaluate(actor, simulator, item_embeddings, states, K, random_baseline=True)

print(f"Average reward (actor): {avg_reward_actor:.4f}")
print(f"Average reward (random): {avg_reward_random:.4f}")
print(f"Improvement: {((avg_reward_actor / avg_reward_random) - 1) * 100:.2f}%")
