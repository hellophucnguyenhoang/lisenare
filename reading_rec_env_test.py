from reading_rec_env import ReadingRecEnvContinuous
import numpy as np
from app.services.item_embeddings import load_all_item_embeddings
from sqlmodel import Session, create_engine


engine = create_engine("sqlite:///database.db")

with Session(engine) as session:
    reading_embeddings = load_all_item_embeddings(session)

env = ReadingRecEnvContinuous(item_embeddings=reading_embeddings)

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
env.close()