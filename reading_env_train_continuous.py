# train_ppo_user_sim_continuous_simple.py
import os
import numpy as np
import matplotlib.pyplot as plt
from sqlmodel import Session, create_engine
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from app.services.item_embeddings import get_reduced_item_embeddings
from reading_env import ReadingRecEnvContinuous

# ---------------------------
# Configuration
# ---------------------------
OUTPUT_DIR = "./training_output_continuous"
os.makedirs(OUTPUT_DIR, exist_ok=True)
MODEL_PATH = os.path.join(OUTPUT_DIR, "ppo_user_sim_continuous.zip")
PLOT_PATH = os.path.join(OUTPUT_DIR, "ppo_eval_rewards_continuous.png")
REWARDS_NPY = os.path.join(OUTPUT_DIR, "ppo_eval_rewards_continuous.npy")
LOG_DIR = os.path.join(OUTPUT_DIR, "tensorboard")

TOTAL_TIMESTEPS = 1000000
EVAL_EPISODES = 100
MAX_STEPS_PER_EPISODE = 50

# ---------------------------
# Load item embeddings
# ---------------------------
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, _, _ = get_reduced_item_embeddings(session)
print(f"reading_embeddings.shape{reading_embeddings.shape}")
# ---------------------------
# Environment creation
# ---------------------------
def make_env():
    def _init():
        env = ReadingRecEnvContinuous(
            reading_embeddings,
            max_steps=MAX_STEPS_PER_EPISODE
        )
        return Monitor(env)
    return _init

env = DummyVecEnv([make_env()])

# ---------------------------
# Train PPO
# ---------------------------
print("🚀 Starting PPO training...")
model = PPO(
    "MlpPolicy",
    env,
    verbose=1,
    learning_rate=3e-4,
    n_steps=512,
    batch_size=64,
    gamma=0.95,
    tensorboard_log=LOG_DIR
)

model.learn(total_timesteps=TOTAL_TIMESTEPS)
model.save(MODEL_PATH)
print(f"✅ Model saved to {MODEL_PATH}")

# ---------------------------
# Evaluate model
# ---------------------------
print("🎯 Evaluating model...")
eval_env = ReadingRecEnvContinuous(reading_embeddings, max_steps=MAX_STEPS_PER_EPISODE)
episode_rewards = []

for ep in range(EVAL_EPISODES):
    obs, _ = eval_env.reset()
    total_reward = 0.0
    for _ in range(MAX_STEPS_PER_EPISODE):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, truncated, _ = eval_env.step(action)
        total_reward += reward
        if done or truncated:
            break
    episode_rewards.append(total_reward)

episode_rewards = np.array(episode_rewards)
np.save(REWARDS_NPY, episode_rewards)
print(f"💾 Saved evaluation rewards to {REWARDS_NPY}")

# ---------------------------
# Plot results
# ---------------------------
plt.figure(figsize=(10, 5))
plt.plot(episode_rewards, label="Episode total reward", alpha=0.6)
if len(episode_rewards) >= 5:
    ma = np.convolve(episode_rewards, np.ones(5)/5, mode="valid")
    plt.plot(range(4, 4 + len(ma)), ma, label="5-episode moving average", linewidth=2)
plt.title("PPO Evaluation Rewards (Continuous Action)")
plt.xlabel("Episode")
plt.ylabel("Total Reward")
plt.legend()
plt.grid(True, linestyle="--", alpha=0.4)
plt.tight_layout()
plt.savefig(PLOT_PATH)
print(f"📊 Saved reward plot to {PLOT_PATH}")
print("✅ Done!")
