import numpy as np
import matplotlib.pyplot as plt
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.monitor import Monitor
from reading_env import ReadingRecEnvContinuous
from sqlmodel import Session, create_engine
from app.services.item_embeddings import get_all_embeddings

# ---------------------------
# Parameters
# ---------------------------
MODEL_PATH = "./training_output_continuous/ppo_user_sim_continuous.zip"
EVAL_EPISODES = 100
RANDOM_EVAL_EPISODES = 1000  # reduce for faster evaluation

# ---------------------------
# Load embeddings from DB
# ---------------------------
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, item_ids = get_all_embeddings(session)
print("Loaded reading embeddings from DB:", reading_embeddings.shape)

# ---------------------------
# Create environment and wrap with Monitor
# ---------------------------
env = ReadingRecEnvContinuous(reading_embeddings)
eval_env = Monitor(env)  # Wrap with Monitor

# Load model
model = PPO.load(MODEL_PATH, env=eval_env)

# ---------------------------
# 1️⃣ Evaluate PPO (stochastic)
# ---------------------------
rewards_ppo, _ = evaluate_policy(
    model, eval_env, n_eval_episodes=EVAL_EPISODES, deterministic=False, return_episode_rewards=True
)
mean_reward_ppo = np.mean(rewards_ppo)
std_reward_ppo = np.std(rewards_ppo)
print(f"PPO Mean Reward (stochastic): {mean_reward_ppo:.3f} ± {std_reward_ppo:.3f}")

# ---------------------------
# PPO (deterministic)
# ---------------------------
rewards_det, _ = evaluate_policy(
    model, eval_env, n_eval_episodes=EVAL_EPISODES, deterministic=True, return_episode_rewards=True
)
mean_reward_det = np.mean(rewards_det)
std_reward_det = np.std(rewards_det)
print(f"PPO Mean Reward (deterministic): {mean_reward_det:.3f} ± {std_reward_det:.3f}")

# ---------------------------
# 2️⃣ Evaluate Random baseline
# ---------------------------
random_rewards = []
for ep in range(RANDOM_EVAL_EPISODES):
    obs, _ = eval_env.reset()
    done = False
    total_reward = 0
    while not done:
        action = eval_env.action_space.sample()  # random vector
        obs, reward, terminated, truncated, _ = eval_env.step(action)
        total_reward += reward
        done = terminated or truncated
    random_rewards.append(total_reward)

mean_random = np.mean(random_rewards)
std_random = np.std(random_rewards)
print(f"Random Mean Reward: {mean_random:.3f} ± {std_random:.3f}")

# ---------------------------
# 3️⃣ Evaluate Cosine-Similarity baseline
# ---------------------------
cosine_rewards = []
for ep in range(RANDOM_EVAL_EPISODES):
    obs, _ = eval_env.reset()
    done = False
    total_reward = 0
    while not done:
        obs_norm = obs / (np.linalg.norm(obs) + 1e-12)
        sims = [np.dot(obs_norm[:env.emb_dim], emb / (np.linalg.norm(emb) + 1e-12)) for emb in env.item_db]
        action = env.item_db[np.argmax(sims)]
        obs, reward, terminated, truncated, _ = eval_env.step(action)
        total_reward += reward
        done = terminated or truncated
    cosine_rewards.append(total_reward)

mean_cosine = np.mean(cosine_rewards)
std_cosine = np.std(cosine_rewards)
print(f"Cosine-Sim Mean Reward: {mean_cosine:.3f} ± {std_cosine:.3f}")

# ---------------------------
# 4️⃣ Compare all
# ---------------------------
print("\n=== Summary ===")
print(f"PPO (stochastic)   : {mean_reward_ppo:.3f} ± {std_reward_ppo:.3f}")
print(f"PPO (deterministic): {mean_reward_det:.3f} ± {std_reward_det:.3f}")
print(f"Random             : {mean_random:.3f} ± {std_random:.3f}")
print(f"Cosine-Sim         : {mean_cosine:.3f} ± {std_cosine:.3f}")

improve_random = (mean_reward_ppo - mean_random) / (abs(mean_random) + 1e-8) * 100
improve_cosine = (mean_reward_ppo - mean_cosine) / (abs(mean_cosine) + 1e-8) * 100
print(f"✅ PPO improves over random baseline by {improve_random:.2f}%")
print(f"✅ PPO improves over cosine-sim baseline by {improve_cosine:.2f}%")

# ---------------------------
# 5️⃣ Plot and save reward distributions
# ---------------------------
# plt.figure(figsize=(10, 6))
# plt.hist(random_rewards, bins=30, alpha=0.6, label="Random")
# plt.hist(cosine_rewards, bins=30, alpha=0.6, label="Cosine-Sim")
# plt.hist(rewards_ppo, bins=30, alpha=0.6, label="PPO Stochastic")
# plt.hist(rewards_det, bins=30, alpha=0.6, label="PPO Deterministic")
# plt.xlabel("Total Episode Reward")
# plt.ylabel("Frequency")
# plt.title("Reward Distributions")
# plt.legend()
# plt.tight_layout()
# plt.savefig("reward_distributions.png")
# print("✅ Reward distributions saved to 'reward_distributions.png'")

import matplotlib.pyplot as plt
import seaborn as sns

# Use Seaborn style for nicer plots
sns.set(style="whitegrid")

plt.figure(figsize=(10, 6))

# Plot each distribution using a kernel density estimate (smoothed curve)
sns.kdeplot(random_rewards, fill=True, alpha=0.4, label="Random")
sns.kdeplot(cosine_rewards, fill=True, alpha=0.4, label="Cosine-Sim")
sns.kdeplot(rewards_ppo, fill=True, alpha=0.4, label="PPO Stochastic")
sns.kdeplot(rewards_det, fill=True, alpha=0.4, label="PPO Deterministic")

plt.xlabel("Total Episode Reward")
plt.ylabel("Density")
plt.title("Reward Distributions Across Policies")
plt.legend()
plt.tight_layout()
plt.savefig("reward_distributions_curve.png")
print("✅ Reward distributions saved to 'reward_distributions_curve.png'")
