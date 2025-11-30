# train_ppo_gridsearch.py
import os
import numpy as np
import matplotlib.pyplot as plt
from sqlmodel import Session, create_engine
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from app.services.item_embeddings import get_all_embeddings
from reading_env import ReadingRecEnvContinuous

# ---------------------------
# Configuration
# ---------------------------
OUTPUT_DIR = "./training_output_continuous"
os.makedirs(OUTPUT_DIR, exist_ok=True)
LOG_DIR = os.path.join(OUTPUT_DIR, "tensorboard")

TOTAL_TIMESTEPS = 1_000_000
EVAL_EPISODES = 100

# Grid search parameter (only n_steps now)
n_steps_list = [512, 1024, 2048]

# Initial LR (will decay automatically)
INITIAL_LR = 1e-3
MIN_LR = 3e-4   # your requested minimum value


# ---------------------------
# LR Schedule (linear decay)
# ---------------------------
def linear_lr_schedule(initial_lr, min_lr):
    """
    Linear LR decay: from initial_lr → min_lr.
    progress_remaining = 1.0 → 0.0 during training
    """
    def schedule(progress_remaining):
        return min_lr + (initial_lr - min_lr) * progress_remaining
    return schedule


# ---------------------------
# Load item embeddings
# ---------------------------
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, _ = get_all_embeddings(session)
print(f"reading_embeddings.shape: {reading_embeddings.shape}")


# ---------------------------
# Environment creation
# ---------------------------
def make_env():
    def _init():
        env = ReadingRecEnvContinuous(reading_embeddings)
        return Monitor(env)
    return _init

env = DummyVecEnv([make_env()])


# ---------------------------
# Grid search training
# ---------------------------
stt = 1
for n_steps in n_steps_list:
    print(f"\n🚀 Starting training {stt}: n_steps={n_steps}, lr_schedule={INITIAL_LR}→{MIN_LR}")

    # Output paths
    model_name = f"reading_rec_{stt}_{n_steps}"
    model_path = os.path.join(OUTPUT_DIR, f"ppo_{model_name}.zip")
    rewards_npy = os.path.join(OUTPUT_DIR, f"ppo_rewards_{model_name}.npy")
    plot_path = os.path.join(OUTPUT_DIR, f"ppo_plot_{model_name}.png")
    run_log_dir = os.path.join(LOG_DIR, f"run_{model_name}")
    os.makedirs(run_log_dir, exist_ok=True)

    # PPO model with LR schedule
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        gamma=0.95,
        batch_size=128,
        learning_rate=linear_lr_schedule(INITIAL_LR, MIN_LR),  # <--- LR schedule
        n_steps=n_steps,
        tensorboard_log=run_log_dir
    )

    # Train
    model.learn(total_timesteps=TOTAL_TIMESTEPS)
    model.save(model_path)
    print(f"✅ Model saved to {model_path}")

    # Evaluate
    print("🎯 Evaluating model...")
    eval_env = ReadingRecEnvContinuous(reading_embeddings)
    episode_rewards = []

    for ep in range(EVAL_EPISODES):
        obs, _ = eval_env.reset()
        total_reward = 0.0
        while True:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, _ = eval_env.step(action)
            total_reward += reward
            if terminated or truncated:
                break
        episode_rewards.append(total_reward)

    episode_rewards = np.array(episode_rewards)
    np.save(rewards_npy, episode_rewards)
    print(f"💾 Saved evaluation rewards to {rewards_npy}")

    # Plot
    plt.figure(figsize=(10, 5))
    plt.plot(episode_rewards, label="Episode total reward", alpha=0.6)

    if len(episode_rewards) >= 5:
        ma = np.convolve(episode_rewards, np.ones(5)/5, mode="valid")
        plt.plot(range(4, 4 + len(ma)), ma, label="5-episode moving average", linewidth=2)

    plt.title(f"PPO Evaluation Rewards (n_steps={n_steps})")
    plt.xlabel("Episode")
    plt.ylabel("Total Reward")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()
    print(f"📊 Saved reward plot to {plot_path}")

    stt += 1

print("✅ All grid search runs completed!")
