import torch
from lird_train import Actor, Critic, Simulator, evaluate, item_embeddings, historical_data, N, K, EMBED_DIM
from app.database import get_session
from app.services.item_embeddings import load_random_item_embeddings
from app.config import settings

# Instantiate models
actor = Actor(state_dim=EMBED_DIM, action_dim=EMBED_DIM, hidden_dim=EMBED_DIM)
critic = Critic(state_dim=EMBED_DIM, action_dim=EMBED_DIM, hidden_dim=EMBED_DIM)
simulator = Simulator(historical_data)

# Load saved weights
checkpoint = torch.load("actor_critic.pth", map_location="cpu")
actor.load_state_dict(checkpoint["actor"])
critic.load_state_dict(checkpoint["critic"])

actor.eval()
critic.eval()


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
