import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.monitor import Monitor

from reading_env import ReadingRecEnvContinuous
from sqlmodel import Session, create_engine
from app.services.item_embeddings import get_all_embeddings

# ========================================================
# Config
# ========================================================
MODEL_PATHS = [
    "training_output_continuous/ppo_reading_rec_1_512.zip",
    "training_output_continuous/ppo_reading_rec_2_1024.zip",
    "training_output_continuous/ppo_reading_rec_3_2048.zip",
]

EVAL_EPISODES = 10000

# ========================================================
# Load embeddings
# ========================================================
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, item_ids = get_all_embeddings(session)
print("Loaded reading embeddings:", reading_embeddings.shape)

# ========================================================
# Create evaluation env (wrapped with Monitor)
# ========================================================
env = ReadingRecEnvContinuous(reading_embeddings)
eval_env = Monitor(env)

# ========================================================
# Function to evaluate one model
# ========================================================
def evaluate_one(model_path):
    print("\n==============================")
    print(f" Evaluating: {model_path}")
    print("==============================")

    model = PPO.load(model_path, env=eval_env)

    # Stochastic
    rewards_sto, _ = evaluate_policy(
        model, eval_env,
        n_eval_episodes=EVAL_EPISODES,
        deterministic=False,
        return_episode_rewards=True,
    )
    rewards_sto = np.array(rewards_sto)

    # Deterministic
    rewards_det, _ = evaluate_policy(
        model, eval_env,
        n_eval_episodes=EVAL_EPISODES,
        deterministic=True,
        return_episode_rewards=True,
    )
    rewards_det = np.array(rewards_det)

    print(
        f"Stochastic : {rewards_sto.mean():.3f} ± {rewards_sto.std():.3f}"
    )
    print(
        f"Deterministic : {rewards_det.mean():.3f} ± {rewards_det.std():.3f}"
    )

    return rewards_sto, rewards_det


# ========================================================
# Evaluate all models
# ========================================================
all_rewards = {}  # Dictionary { label: rewards }

for i, path in enumerate(MODEL_PATHS, start=1):
    r_sto, r_det = evaluate_one(path)

    all_rewards[f"Model_{i}_Stochastic"] = r_sto
    all_rewards[f"Model_{i}_Deterministic"] = r_det

print("\n===== DONE Evaluation =====")

# ========================================================
# Plot reward distributions for all 6 versions
# ========================================================
# sns.set_theme(style="whitegrid")
# plt.figure(figsize=(12, 8))

# for label, rewards in all_rewards.items():
#     sns.kdeplot(
#         rewards, fill=True, alpha=0, linewidth=1.5, label=label
#     )

# plt.xlabel("Total Episode Reward")
# plt.ylabel("Density")
# plt.title("Reward Distributions for 3 PPO Models (Stochastic & Deterministic)")
# plt.legend()
# plt.tight_layout()
# plt.savefig("reward_distributions_all_models.png", dpi=300)
# print("\n🎉 Saved plot to reward_distributions_all_models.png")

sns.set_theme(style="whitegrid")
plt.figure(figsize=(12, 8))

for label, rewards in all_rewards.items():
    if "Stochastic" in label:
        sns.kdeplot(
            rewards, fill=True, alpha=0, linewidth=1.5, label=label
        )

plt.xlabel("Total Episode Reward")
plt.ylabel("Density")
plt.title("Reward Distributions for 3 PPO Models (Stochastic)")
plt.legend()
plt.tight_layout()
plt.savefig("reward_distributions_all_models_stochastic.png", dpi=300)
print("\n🎉 Saved plot to reward_distributions_all_models_stochastic.png")


sns.set_theme(style="whitegrid")
plt.figure(figsize=(12, 8))

for label, rewards in all_rewards.items():
    if "Deterministic" in label:
        sns.kdeplot(
            rewards, fill=True, alpha=0, linewidth=1.5, label=label
        )

plt.xlabel("Total Episode Reward")
plt.ylabel("Density")
plt.title("Reward Distributions for 3 PPO Models (Deterministic)")
plt.legend()
plt.tight_layout()
plt.savefig("reward_distributions_all_models_deterministic.png", dpi=300)
print("\n🎉 Saved plot to reward_distributions_all_models_deterministic.png")