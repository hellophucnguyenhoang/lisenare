from reading_rec_env import ReadingRecEnvContinuous
import numpy as np
from app.services.item_embeddings import get_all_item_embeddings
from sqlmodel import Session, create_engine


engine = create_engine("sqlite:///database.db")

with Session(engine) as session:
    reading_embeddings, _ = get_all_item_embeddings(session)

env = ReadingRecEnvContinuous(item_embeddings=reading_embeddings)


# ---------------------------
# Random running test
# ---------------------------
# Reset environment to start a new episode
observation, info = env.reset()

episode_over = False
total_reward = 0

while False: # not episode_over:
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
    # pick the embedding most similar to current recommendation_state
    obs_norm = obs / (np.linalg.norm(obs) + 1e-12)
    sims = [np.dot(obs_norm[:env.emb_dim], emb / (np.linalg.norm(emb) + 1e-12)) for emb in env.item_embeddings]
    # now action = chosen embedding vector
    action = env.item_embeddings[np.argmax(sims)]
    obs, reward, terminated, truncated, info = env.step(action)
    print(reward, info)
    total_reward += reward
    episode_over = terminated or truncated

print(f"Episode finished! Total reward: {total_reward}")
env.close()
