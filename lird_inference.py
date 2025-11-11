import torch
from lird_train import Actor, Critic, select_action
from app.database import get_session
from app.services.item_embeddings import get_random_embeddings
import torch.nn as nn
from app.config import settings

# Hyperparameters must match training
EMBED_DIM = settings.item_embedding_dim  # d = n
N = 4
K = 3
NUM_ITEMS = 200

# Instantiate models
actor = Actor(state_dim=EMBED_DIM, action_dim=EMBED_DIM, hidden_dim=EMBED_DIM)
critic = Critic(state_dim=EMBED_DIM, action_dim=EMBED_DIM, hidden_dim=EMBED_DIM)

# Load saved weights
checkpoint = torch.load("actor_critic.pth", map_location="cpu")
actor.load_state_dict(checkpoint["actor"])
critic.load_state_dict(checkpoint["critic"])

# Set to evaluation mode
actor.eval()
critic.eval()

# Load item embeddings
with next(get_session()) as session:
    item_embeddings = get_random_embeddings(session, NUM_ITEMS, EMBED_DIM)

# Build a dummy state for inference
state_idx = torch.randint(0, item_embeddings.size(0), (N,))
state = item_embeddings[state_idx]

# Select action
with torch.no_grad():
    action = select_action(actor, state, item_embeddings)  # (K, EMBED_DIM)

print("Action embeddings shape:", action.shape)
