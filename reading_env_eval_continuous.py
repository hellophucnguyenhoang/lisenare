import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy
from reading_rec_env import ReadingRecEnvContinuous  # <- đổi import
from sqlmodel import Session, create_engine, select
from app.models import Reading
from app.services.item_embeddings import get_all_item_embeddings

# ---------------------------
# Parameters
# ---------------------------
MODEL_PATH = "./training_output_continuous/ppo_user_sim_continuous.zip"
EVAL_EPISODES = 100
RANDOM_EVAL_EPISODES = 1000  # giảm để đánh giá nhanh

# ---------------------------
# Load embeddings from DB
# ---------------------------
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, _ = get_all_item_embeddings(session)
print("Loaded reading embeddings from DB:", reading_embeddings.shape)

# ---------------------------
# Create environment
# ---------------------------
env = ReadingRecEnvContinuous(reading_embeddings)
model = PPO.load(MODEL_PATH, env=env)

# ---------------------------
# 1️⃣ Evaluate PPO
# ---------------------------
mean_reward_ppo, std_reward_ppo = evaluate_policy(model, env, n_eval_episodes=EVAL_EPISODES, deterministic=False)
print(f"PPO Mean Reward: {mean_reward_ppo:.3f} ± {std_reward_ppo:.3f}")

# ---------------------------
# 2️⃣ Evaluate Random baseline
# ---------------------------
random_rewards = []
for ep in range(RANDOM_EVAL_EPISODES):
    obs, _ = env.reset()
    done = False
    total_reward = 0
    while not done:
        action = env.action_space.sample()  # random vector in [-1,1]
        obs, reward, terminated, truncated, _ = env.step(action)
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
    obs, _ = env.reset()
    done = False
    total_reward = 0
    while not done:
        # pick the embedding most similar to current recommendation_state
        obs_norm = obs / (np.linalg.norm(obs) + 1e-12)
        sims = [np.dot(obs_norm, emb / (np.linalg.norm(emb) + 1e-12)) for emb in env.item_embeddings]
        # now action = chosen embedding vector
        action = env.item_embeddings[np.argmax(sims)]
        obs, reward, terminated, truncated, _ = env.step(action)
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
print(f"PPO      : {mean_reward_ppo:.3f} ± {std_reward_ppo:.3f}")
print(f"Random   : {mean_random:.3f} ± {std_random:.3f}")
print(f"Cosine   : {mean_cosine:.3f} ± {std_cosine:.3f}")

improve_random = (mean_reward_ppo - mean_random) / (abs(mean_random) + 1e-8) * 100
print(f"✅ PPO improves over random baseline by {improve_random:.2f}%")

improve_cosine = (mean_reward_ppo - mean_cosine) / (abs(mean_cosine) + 1e-8) * 100
print(f"✅ PPO improves over cosine-sim baseline by {improve_cosine:.2f}%")
