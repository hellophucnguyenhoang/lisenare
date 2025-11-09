import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy
from reading_rec_env import ReadingRecEnv
from sqlmodel import Session, create_engine, select
from app.services.item_embeddings import get_item_embedding_by_reading_id
from app.models import Reading

# ---------------------------
# Parameters
# ---------------------------
MODEL_PATH = "./training_output/ppo_user_sim.zip"
EVAL_EPISODES = 100
RANDOM_EVAL_EPISODES = 1000  # reduce from 100k to speed up

# ---------------------------
# Load embeddings from DB
# ---------------------------
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_ids = session.exec(select(Reading.id)).all()
    reading_embeddings = []
    for rid in reading_ids:
        vec = get_item_embedding_by_reading_id(session, rid)
        if vec is not None:
            reading_embeddings.append(vec)
        else:
            print(f"Warning: No embedding for reading id {rid}")

reading_embeddings = np.array(reading_embeddings, dtype=np.float32)
print("Loaded reading embeddings from DB:", reading_embeddings.shape)

# ---------------------------
# Create environment
# ---------------------------
env = ReadingRecEnv(reading_embeddings)
model = PPO.load(MODEL_PATH, env=env)

# ---------------------------
# 1️⃣ Evaluate PPO
# ---------------------------
mean_reward_ppo, std_reward_ppo = evaluate_policy(model, env, n_eval_episodes=EVAL_EPISODES)
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
        action = env.action_space.sample()
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
        # pick the exercise whose embedding is most similar to current user_state
        sims = [
            np.dot(obs, emb) / (np.linalg.norm(obs) * np.linalg.norm(emb) + 1e-12)
            for emb in env.reading_embeddings
        ]
        action = int(np.argmax(sims))
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
print(f"Random   : {mean_random:.3f} ± {std_random:.3f}")
print(f"Cosine   : {mean_cosine:.3f} ± {std_cosine:.3f}")
print(f"PPO      : {mean_reward_ppo:.3f} ± {std_reward_ppo:.3f}")
improve_cosine = (mean_reward_ppo - mean_cosine) / (abs(mean_cosine) + 1e-8) * 100
print(f"✅ PPO improves over cosine-sim baseline by {improve_cosine:.2f}%")
