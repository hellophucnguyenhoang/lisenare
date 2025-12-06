import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.monitor import Monitor
from sqlmodel import Session, create_engine

from reading_env import ReadingRecEnvContinuous
from app.services.item_embeddings import get_all_embeddings

# ---------------------------
# Parameters
# ---------------------------
MODEL_PATH = "./training_output_continuous/ppo_reading_rec_3_2048.zip"
EVAL_EPISODES = 10000
RANDOM_EVAL_EPISODES = EVAL_EPISODES

# ---------------------------
# Load embeddings from DB
# ---------------------------
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, item_ids = get_all_embeddings(session)
print("Loaded embeddings:", reading_embeddings.shape)

# ---------------------------
# Create environment
# ---------------------------
env = ReadingRecEnvContinuous(reading_embeddings)
eval_env = Monitor(env)

model = PPO.load(MODEL_PATH, env=eval_env)

# To store all rewards
results = {}

# ---------------------------
# 1️⃣ PPO (stochastic)
# ---------------------------
rewards_ppo, _ = evaluate_policy(
    model, eval_env,
    n_eval_episodes=EVAL_EPISODES,
    deterministic=False,
    return_episode_rewards=True
)
results["ppo_stoch"] = np.array(rewards_ppo)

print(f"PPO stochastic: {np.mean(rewards_ppo):.3f} ± {np.std(rewards_ppo):.3f}")

# ---------------------------
# 2️⃣ PPO (deterministic)
# ---------------------------
rewards_det, _ = evaluate_policy(
    model, eval_env,
    n_eval_episodes=EVAL_EPISODES,
    deterministic=True,
    return_episode_rewards=True
)
results["ppo_det"] = np.array(rewards_det)

print(f"PPO deterministic: {np.mean(rewards_det):.3f} ± {np.std(rewards_det):.3f}")

# ---------------------------
# 3️⃣ Random baseline (chọn random ID → lấy embedding tương ứng)
# ---------------------------
random_rewards = []
num_items = len(env.item_db)

for ep in range(RANDOM_EVAL_EPISODES):
    obs, _ = eval_env.reset()
    done = False
    total_reward = 0

    while not done:
        # Random item index
        rand_idx = np.random.randint(0, num_items)

        # Lấy embedding tương ứng để dùng làm hành động
        action = env.item_db[rand_idx]

        # Step như bình thường
        obs, reward, terminated, truncated, _ = eval_env.step(action)
        total_reward += reward
        done = terminated or truncated

    random_rewards.append(total_reward)

results["random"] = np.array(random_rewards)

print(f"Random: {np.mean(random_rewards):.3f} ± {np.std(random_rewards):.3f}")

# ---------------------------
# 4️⃣ Cosine similarity baseline
# ---------------------------
cosine_rewards = []
for ep in range(RANDOM_EVAL_EPISODES):
    obs, _ = eval_env.reset()
    done = False
    total_reward = 0
    while not done:
        obs_norm = obs / (np.linalg.norm(obs) + 1e-12)
        sims = [
            np.dot(obs_norm[:env.emb_dim], emb / (np.linalg.norm(emb) + 1e-12))
            for emb in env.item_db
        ]
        action = env.item_db[np.argmax(sims)]
        obs, reward, terminated, truncated, _ = eval_env.step(action)
        total_reward += reward
        done = terminated or truncated

    cosine_rewards.append(total_reward)

results["cosine"] = np.array(cosine_rewards)

print(f"Cosine: {np.mean(cosine_rewards):.3f} ± {np.std(cosine_rewards):.3f}")

# ---------------------------
# 5️⃣ Save all results for later analysis
# ---------------------------
np.savez(
    "eval_rewards.npz",
    ppo_stoch=results["ppo_stoch"],
    ppo_det=results["ppo_det"],
    random=results["random"],
    cosine=results["cosine"],
)
print("💾 Saved rewards to eval_rewards.npz")

# ---------------------------
# 6️⃣ Plot KDE curves
# ---------------------------
sns.set_theme(style="whitegrid")

plt.figure(figsize=(10, 6))
sns.kdeplot(results["random"], fill=True, alpha=0.2, label="Random")
sns.kdeplot(results["cosine"], fill=True, alpha=0.2, label="Cosine-Sim")
sns.kdeplot(results["ppo_stoch"], fill=True, alpha=0.2, label="PPO Stochastic")
sns.kdeplot(results["ppo_det"], fill=True, alpha=0.2, label="PPO Deterministic")

plt.xlabel("Total Episode Reward")
plt.ylabel("Density")
plt.title("Reward Distributions Across Policies")
plt.legend()
plt.tight_layout()
plt.savefig("reward_distributions_curve.png")
print("📈 Saved reward distributions to reward_distributions_curve.png")
