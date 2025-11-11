import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
from copy import deepcopy
import random
from app.config import settings
import pickle
from app.database import get_session
from app.services.item_embeddings import get_random_embeddings
from app.config import settings

# Hyperparameters
EMBED_DIM = settings.item_embedding_dim  # d = n
N = 5   # Number of items in state
K = 3    # Number of items to recommend
NUM_ITEMS = 200
ALPHA = 0.5     # for cosine
GAMMA_REWARD = 0.9  # position discount Γ
GAMMA = 0.99    # discount factor
TAU = 0.001     # soft update
BATCH_SIZE = 32
REPLAY_SIZE = 1000
LR_ACTOR = 1e-4
LR_CRITIC = 1e-3
NUM_EPISODES = 10  # small for demo
EPISODE_LEN = 20   # T

# # Dummy item embeddings: (NUM_ITEMS, EMBED_DIM)
# item_embeddings = torch.randn(NUM_ITEMS, EMBED_DIM)

# Dummy historical data for simulator: list of triples ((s, a), r_vec)
# s: (N, EMBED_DIM), a: (K, EMBED_DIM), r_vec: (K,)
# NUM_HIST = 1000
# historical_data = []
# for _ in range(NUM_HIST):
#     s = item_embeddings[torch.randint(0, NUM_ITEMS, (N,))]
#     a = item_embeddings[torch.randint(0, NUM_ITEMS, (K,))]
#     r_vec = torch.tensor(random.choices([0, 0.1, 0.5, 0.8, 1.0], k=K))  # skip/view/click/submit/like
#     historical_data.append(((s, a), r_vec))

with next(get_session()) as session:
    item_embeddings = get_random_embeddings(session, NUM_ITEMS, EMBED_DIM)

print(f"Loaded item embeddings with shape: {item_embeddings.shape}")  # (num_items_loaded, EMBED_DIM)

# ---------------------------------------
# # Load historical_data từ file
# ---------------------------------------
# with open("historical_data.pkl", "rb") as f:
#     historical_data = pickle.load(f)

def generate_synthetic_history(item_embeddings, num_hist=10000, n=5, k=3):
    """
    Generate synthetic historical interaction data based on item difficulty similarity.

    Args:
        item_embeddings (torch.Tensor): [num_items, embed_dim] full embedding matrix.
        num_hist (int): number of historical entries to generate.
        n (int): number of items in each state.
        k (int): number of items in each action list.

    Returns:
        list[ ((state, action), r_vec) ]: synthetic historical data.
    """

    num_items, embed_dim = item_embeddings.shape
    DIFF_START = 384
    DIFF_END = 390  # one-hot difficulty (6 dims)

    INTERACTION_SCALE = {
        -1.0: 0.05,  # dislike
        -0.25: 0.05, # skip
        0.1: 0.1,    # view
        0.5: 0.3,    # click
        0.8: 0.3,    # submit
        1.0: 0.2     # like
    }

    def compute_reaction_prob(state_diffs, action_diff):
        """Compute probability of each reaction based on difficulty similarity."""
        state_mean = state_diffs.mean(0)  # (6,)
        action_vec = action_diff
        sim = float((state_mean * action_vec).sum())  # similarity ∈ [0,1]
        probs = []
        for r, base in INTERACTION_SCALE.items():
            if r >= 0:
                probs.append(base * (0.5 + sim))  # favor positive if similar
            else:
                probs.append(base * (1.0 - sim))  # favor negative if dissimilar
        total = sum(probs)
        return [p / total for p in probs]

    historical_data = []

    for _ in range(num_hist):
        # initial state
        state_idx = torch.randint(0, num_items, (n,))
        state = item_embeddings[state_idx]
        state_diffs = state[:, DIFF_START:DIFF_END]

        # action
        action_idx = torch.randint(0, num_items, (k,))
        action = item_embeddings[action_idx]

        # generate rewards
        r_vec_list = []
        for i in range(k):
            action_diff = action[i, DIFF_START:DIFF_END]
            probs = compute_reaction_prob(state_diffs, action_diff)
            r_val = random.choices(list(INTERACTION_SCALE.keys()), weights=probs)[0]
            r_vec_list.append(r_val)
        r_vec = torch.tensor(r_vec_list, dtype=torch.float)

        # store
        historical_data.append(((state, action), r_vec))

        # update state (push positive interactions)
        interacted = [action[i] for i in range(k) if r_vec[i] > 0]
        if interacted:
            interacted_tensor = torch.stack(interacted)
            if len(interacted) >= n:
                state = interacted_tensor[-n:]
            else:
                keep_num = n - len(interacted)
                state = torch.cat([state[-keep_num:], interacted_tensor], dim=0)

    print(f"✅ Generated {len(historical_data)} synthetic entries.")
    print(f"Example state shape: {historical_data[0][0][0].shape}")
    print(f"Example action shape: {historical_data[0][0][1].shape}")
    print(f"Example reward vector: {historical_data[0][1]}")
    return historical_data

historical_data = generate_synthetic_history(item_embeddings, num_hist=10000, n=N, k=K)


class Simulator:
    def __init__(self, historical_data, alpha=ALPHA):
        self.alpha = alpha
        self.groups = {}  # group by r_vec tuple
        for (s, a), r_vec in historical_data:
            r_tuple = tuple(r_vec.tolist())
            if r_tuple not in self.groups:
                self.groups[r_tuple] = {'s_list': [], 'a_list': []}
            s_mean = s.mean(0)
            s_norm = s_mean / (s_mean.norm() + 1e-8)
            a_mean = a.mean(0)
            a_norm = a_mean / (a_mean.norm() + 1e-8)
            self.groups[r_tuple]['s_list'].append(s_norm)
            self.groups[r_tuple]['a_list'].append(a_norm)
        
        self.Nx = {}
        self.s_bar = {}
        self.a_bar = {}
        for r_tuple, data in self.groups.items():
            Nx = len(data['s_list'])
            s_bar = torch.stack(data['s_list']).mean(0)
            a_bar = torch.stack(data['a_list']).mean(0)
            self.Nx[r_tuple] = Nx
            self.s_bar[r_tuple] = s_bar
            self.a_bar[r_tuple] = a_bar

    def simulate_reward(self, s, a):
        s_mean = s.mean(0)
        s_norm = s_mean / (s_mean.norm() + 1e-8)
        a_mean = a.mean(0)
        a_norm = a_mean / (a_mean.norm() + 1e-8)

        probs = []
        r_tuples = list(self.Nx.keys())
        for r_tuple in r_tuples:
            state_sim = self.alpha * (s_norm @ self.s_bar[r_tuple])
            action_sim = (1 - self.alpha) * (a_norm @ self.a_bar[r_tuple])
            sim = state_sim + action_sim
            prob = self.Nx[r_tuple] * sim
            probs.append(prob)
        
        probs = torch.tensor(probs)
        probs = torch.clamp(probs, min=0)
        if probs.sum() == 0:
            probs = torch.ones_like(probs) / len(probs)
        probs = probs / probs.sum()
        chosen_idx = torch.multinomial(probs, 1).item()
        r_vec = torch.tensor(r_tuples[chosen_idx])
        
        # Overall reward (Eq. 4)
        r = sum(GAMMA_REWARD ** k * r_vec[k] for k in range(K))
        return r, r_vec

class Actor(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_dim=settings.item_embedding_dim):
        super(Actor, self).__init__()
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, action_dim * K)  # output K * d

    def forward(self, state):
        if state.dim() == 2:  # (N, d)
            x = state.mean(0)
        elif state.dim() == 3:  # (B, N, d)
            x = state.mean(1)
        else:
            x = state
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        weights = self.fc3(x)
        if weights.dim() == 1:
            weights = weights.view(K, -1)  # (K, d)
        else:
            weights = weights.view(weights.size(0), K, -1)  # (B, K, d)
        return weights

def select_action(actor, state, item_embeddings):
    weights = actor(state)  # (K, d) or (1, K, d) but since single, (K,d)
    if weights.dim() == 3:
        weights = weights.squeeze(0)
    item_pool = item_embeddings.clone()
    action_list = []
    for k in range(K):
        scores = item_pool @ weights[k]  # (NUM_ITEMS,)
        best_idx = scores.argmax()
        best_item = item_pool[best_idx].clone()
        action_list.append(best_item)
        item_pool = torch.cat([item_pool[:best_idx], item_pool[best_idx+1:]], dim=0)
    action = torch.stack(action_list)  # (K, d)
    return action

def select_action_random(item_embeddings, K):
    """Select K random distinct items from the item pool."""
    num_items = item_embeddings.size(0)
    if K > num_items:
        K = num_items
    idx = torch.randperm(num_items)[:K]
    action = item_embeddings[idx]
    return action

def evaluate(actor, simulator, item_embeddings, states, K, random_baseline=False):
    rewards = []
    for s in states:
        if random_baseline:
            a = select_action_random(item_embeddings, K)
        else:
            a = select_action(actor, s, item_embeddings)
        r, _ = simulator.simulate_reward(s, a)
        rewards.append(r.item())
    return sum(rewards) / len(rewards)

class Critic(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_dim=settings.item_embedding_dim):
        super(Critic, self).__init__()
        total_dim = state_dim + action_dim
        self.fc1 = nn.Linear(total_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, 1)

    def forward(self, state, action):
        if state.dim() == 2:  # single (N,d)
            s = state.mean(0)
        elif state.dim() == 3:  # batch (B,N,d)
            s = state.mean(1)
        else:
            s = state
        
        if action.dim() == 2:  # (K,d)
            a = action.mean(0)
        elif action.dim() == 3:  # (B,K,d)
            a = action.mean(1)
        else:
            a = action
        
        x = torch.cat([s, a], dim=-1 if s.dim() > 0 else 0)
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        q = self.fc3(x).squeeze(-1)  # (B,) or scalar
        return q

class ReplayBuffer:
    def __init__(self, capacity):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state):
        self.buffer.append((state, action, reward, next_state))

    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states = zip(*batch)
        return torch.stack(states), torch.stack(actions), torch.tensor(rewards, dtype=torch.float), torch.stack(next_states)

    def __len__(self):
        return len(self.buffer)


def main():
    # Initialize
    state_dim = EMBED_DIM
    action_dim = EMBED_DIM
    actor = Actor(state_dim, action_dim)
    critic = Critic(state_dim, action_dim)
    target_actor = deepcopy(actor)
    target_critic = deepcopy(critic)
    optimizer_actor = optim.Adam(actor.parameters(), lr=LR_ACTOR)
    optimizer_critic = optim.Adam(critic.parameters(), lr=LR_CRITIC)
    replay_buffer = ReplayBuffer(REPLAY_SIZE)
    simulator = Simulator(historical_data)

    # Training loop
    for episode in range(NUM_EPISODES):
        state_idx = torch.randint(0, NUM_ITEMS, (N,))
        state = item_embeddings[state_idx]  # (N, d)
        episode_reward = 0.0
        
        for t in range(EPISODE_LEN):
            action = select_action(actor, state, item_embeddings)
            reward, r_vec = simulator.simulate_reward(state, action)
            next_state = state.clone()
            added_items = []
            for k in range(K):
                if r_vec[k] > 0:
                    added_items.append(action[k])
            added = len(added_items)
            if added > 0:
                if added == 1:
                    added_tensor = added_items[0].unsqueeze(0)
                else:
                    added_tensor = torch.stack(added_items)
                next_state = torch.cat([next_state[added:], added_tensor], dim=0)
            replay_buffer.push(state, action, reward, next_state)
            state = next_state
            episode_reward += reward

            if len(replay_buffer) >= BATCH_SIZE:
                states, actions, rewards, next_states = replay_buffer.sample(BATCH_SIZE)
                
                # Critic update
                with torch.no_grad():
                    next_actions = torch.stack([select_action(target_actor, ns, item_embeddings) for ns in next_states])
                    target_q = rewards + GAMMA * target_critic(next_states, next_actions)
                
                current_q = critic(states, actions)
                critic_loss = nn.MSELoss()(current_q, target_q)
                optimizer_critic.zero_grad()
                critic_loss.backward()
                torch.nn.utils.clip_grad_norm_(critic.parameters(), 1.0)
                optimizer_critic.step()
                
                # Actor update
                pred_actions = torch.stack([select_action(actor, s, item_embeddings) for s in states])
                actor_loss = -critic(states, pred_actions).mean()
                optimizer_actor.zero_grad()
                actor_loss.backward()
                torch.nn.utils.clip_grad_norm_(actor.parameters(), 1.0)
                optimizer_actor.step()
                
                # Soft updates
                for param, t_param in zip(actor.parameters(), target_actor.parameters()):
                    t_param.data.copy_(TAU * param.data + (1 - TAU) * t_param.data)
                for param, t_param in zip(critic.parameters(), target_critic.parameters()):
                    t_param.data.copy_(TAU * param.data + (1 - TAU) * t_param.data)
        
        print(f"Episode {episode + 1}, Total Reward: {episode_reward}")

    print("Training complete.")

    # Save actor and critic only (state_dict)
    torch.save({
        "actor": actor.state_dict(),
        "critic": critic.state_dict()
    }, "actor_critic.pth")
    print("Models saved to actor_critic.pth")


if __name__ == "__main__":
    main()
