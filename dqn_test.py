# %%
print('HI')

# %%
import torch
import torch.nn as nn

class QNetwork(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_dim=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, state, action):
        # state: (batch, state_dim)
        # action: (batch, action_dim)
        x = torch.cat([state, action], dim=1)
        return self.net(x)

# %%
import numpy as np
import torch
from sklearn.metrics.pairwise import cosine_similarity

def select_action(q_net, state, reading_embeddings, device, K=20, epsilon=0.1, sim_ratio=0.5):
    """
    Select action among K candidates: 50% similar (cosine) + 50% random
    """
    N = len(reading_embeddings)
    n_sim = int(K * sim_ratio)
    n_rand = K - n_sim

    # 1️⃣ Tính cosine similarity giữa user embedding (state[:emb_dim]) và toàn bộ item embeddings
    user_emb = state[:reading_embeddings.shape[1]].reshape(1, -1)
    sims = cosine_similarity(user_emb, reading_embeddings)[0]  # (N,)
    top_idx = np.argsort(sims)[-n_sim:]  # chỉ số các items giống nhất

    # 2️⃣ Lấy thêm random indices
    rand_idx = np.random.choice(N, n_rand, replace=False)
    idx = np.concatenate([top_idx, rand_idx])

    actions = reading_embeddings[idx]  # (K, emb_dim)

    # 3️⃣ Exploration (epsilon-greedy)
    if np.random.rand() < epsilon:
        ridx = np.random.randint(0, K)
        return actions[ridx], idx[ridx]

    # 4️⃣ Đánh giá Q-values cho các candidate actions
    state_t = torch.FloatTensor(state).unsqueeze(0).to(device)
    a_t = torch.FloatTensor(actions).to(device)
    state_rep = state_t.repeat(K, 1)
    q_values = q_net(state_rep, a_t).squeeze().detach().cpu().numpy()

    best_idx = np.argmax(q_values)
    return actions[best_idx], idx[best_idx]

# %%
import torch.optim as optim
from collections import deque
import random
import matplotlib.pyplot as plt


class ReplayBuffer:
    def __init__(self, capacity=1000):
        self.buffer = deque(maxlen=capacity)
    def push(self, *args):
        self.buffer.append(args)
    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        s, a, r, s2, d = map(np.stack, zip(*batch))
        return s, a, r, s2, d
    def __len__(self): return len(self.buffer)

def train_dqn_continuous(env, reading_embeddings, state_dim, action_dim, K=20, 
                         gamma=0.99, lr=1e-3, batch_size=64, 
                         buffer_size=1000, episodes=500, target_update=1000):

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    q_net = QNetwork(state_dim, action_dim).to(device)
    target_net = QNetwork(state_dim, action_dim).to(device)
    target_net.load_state_dict(q_net.state_dict())

    optimizer = optim.Adam(q_net.parameters(), lr=lr)
    replay = ReplayBuffer(buffer_size)
    step_count = 0

    reward_history = []  # 👈 Lưu toàn bộ reward của mỗi episode

    for ep in range(episodes):
        s, _ = env.reset()
        done = False
        ep_reward = 0

        while not done:
            a, a_idx = select_action(q_net, s, reading_embeddings, device, K)
            s_next, r, terminated, truncated, _ = env.step(a)
            done = terminated or truncated
            
            replay.push(s, a, r, s_next, done)
            s = s_next
            ep_reward += r

            # --- Training step ---
            if len(replay) >= batch_size:
                s_b, a_b, r_b, s2_b, done_b = replay.sample(batch_size)
                s_b = torch.FloatTensor(s_b).to(device)
                a_b = torch.FloatTensor(a_b).to(device)
                r_b = torch.FloatTensor(r_b).unsqueeze(1).to(device)
                s2_b = torch.FloatTensor(s2_b).to(device)
                done_mask = torch.FloatTensor(1 - done_b).unsqueeze(1).to(device)

                # Sample next actions
                next_actions = np.stack([
                    reading_embeddings[np.random.choice(len(reading_embeddings), K, replace=False)]
                    for _ in range(batch_size)
                ])
                s2_rep = s2_b.unsqueeze(1).repeat(1, K, 1).view(batch_size * K, state_dim)
                next_actions_flat = torch.FloatTensor(next_actions).view(batch_size * K, action_dim).to(device)

                q_next_flat = target_net(s2_rep, next_actions_flat).view(batch_size, K)
                q_next = q_next_flat.max(1, keepdim=True)[0]

                y = r_b + gamma * q_next * done_mask
                q_pred = q_net(s_b, a_b)

                loss = nn.MSELoss()(q_pred, y.detach())
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            step_count += 1
            if step_count % target_update == 0:
                target_net.load_state_dict(q_net.state_dict())
                print(f"step_count:{step_count}")

        # ✅ Lưu reward mỗi episode
        reward_history.append(ep_reward)

        # ✅ Tính trung bình 10 episode gần nhất
        if len(reward_history) >= 10:
            recent_avg = np.mean(reward_history[-10:])
        else:
            recent_avg = np.mean(reward_history)

        print(f"Episode {ep}: Reward = {ep_reward:.2f}, Recent Avg(10) = {recent_avg:.2f}")

    # ✅ Sau khi train xong → vẽ biểu đồ reward
    plt.figure(figsize=(8, 4))
    plt.plot(reward_history, label="Episode Reward", alpha=0.7)
    window = 10
    moving_avg = np.convolve(reward_history, np.ones(window)/window, mode='valid')
    plt.plot(range(window-1, len(moving_avg)+window-1), moving_avg, label=f"{window}-Episode Moving Avg", linewidth=2)
    plt.xlabel("Episode")
    plt.ylabel("Reward")
    plt.title("Training Reward Curve")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("training_reward.png")  # 💾 Lưu thành ảnh

    return q_net


# %%
from app.services.item_embeddings import get_all_embeddings
from sqlmodel import Session, create_engine, select
from reading_env import ReadingRecEnvContinuous


engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, item_ids = get_all_embeddings(session)

env = ReadingRecEnvContinuous(reading_embeddings)
trained_q_net = train_dqn_continuous(
    env,
    reading_embeddings,
    state_dim=env.observation_space.shape[0],
    action_dim=env.action_space.shape[0],
)

# %%
