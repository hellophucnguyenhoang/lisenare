from reading_env import ReadingRecEnvContinuous
import numpy as np
from app.services.item_embeddings import get_all_embeddings
from sqlmodel import Session, create_engine


engine = create_engine("sqlite:///database.db")

with Session(engine) as session:
    reading_embeddings, item_ids = get_all_embeddings(session)

env = ReadingRecEnvContinuous(reading_embeddings)

# ---------------------------
# Random running test
# ---------------------------
# Reset environment to start a new episode
observation, info = env.reset()

episode_over = False
total_reward = 0

while not episode_over:
    action = env.action_space.sample()

    observation, reward, terminated, truncated, info = env.step(action)
    print(reward, info)
    total_reward += reward
    episode_over = terminated or truncated

print(f"Episode finished! Total reward: {total_reward}")
# env.close()

print("========================================================")

# ---------------------------
# Cosine-Similarity running test
# ---------------------------
obs, _ = env.reset()
episode_over = False
total_reward = 0

while not episode_over:
    # Chuẩn hoá vector quan sát
    obs_norm = obs / (np.linalg.norm(obs) + 1e-12)

    # Tính độ tương đồng cosine cho toàn bộ embedding
    sims = np.array([
        np.dot(obs_norm[:env.emb_dim], emb / (np.linalg.norm(emb) + 1e-12))
        for emb in env.item_db
    ])

    # Chọn item có similarity cao nhất trong các item hợp lệ
    best_idx = np.argmax(sims)
    action = env.item_db[best_idx]

    # Bước tiếp theo trong môi trường
    obs, reward, terminated, truncated, info = env.step(action)
    print(reward, info)
    total_reward += reward
    episode_over = terminated or truncated

print(f"✅ Episode finished! Total reward: {total_reward}")
env.close()

