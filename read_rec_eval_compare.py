import numpy as np
import matplotlib.pyplot as plt
from stable_baselines3 import PPO
from reading_rec_env import ReadingRecEnvContinuous
from sqlmodel import Session, create_engine
from app.services.item_embeddings import get_all_item_embeddings

MODEL_PATH = "./training_output_continuous/ppo_user_sim_continuous.zip"
N_EP_EVAL = 200
RANDOM_EVAL_EPISODES = 1000

# load embeddings
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    reading_embeddings, _ = get_all_item_embeddings(session)

# env for eval (match train config)
env = ReadingRecEnvContinuous(reading_embeddings)

# load model
model = PPO.load(MODEL_PATH, env=env)

def eval_policy_run(model, env, n_eps=200, deterministic=False):
    rewards = []
    for _ in range(n_eps):
        obs, _ = env.reset()
        total = 0.0
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=deterministic)
            obs, r, terminated, truncated, _ = env.step(action)
            total += r
            done = terminated or truncated
        rewards.append(total)
    return np.array(rewards)

# 1) PPO deterministic vs stochastic
ppo_det = eval_policy_run(model, env, n_eps=N_EP_EVAL, deterministic=True)
ppo_sto = eval_policy_run(model, env, n_eps=N_EP_EVAL, deterministic=False)

# 2) Random baseline
random_rewards = []
for _ in range(RANDOM_EVAL_EPISODES):
    obs, _ = env.reset()
    total = 0.0
    done = False
    while not done:
        action = env.action_space.sample()
        obs, r, terminated, truncated, _ = env.step(action)
        total += r
        done = terminated or truncated
    random_rewards.append(total)
random_rewards = np.array(random_rewards)

# 3) Cosine baseline
cosine_rewards = []
for _ in range(RANDOM_EVAL_EPISODES):
    obs, _ = env.reset()
    total = 0.0
    done = False
    while not done:
        obs_norm = obs / (np.linalg.norm(obs) + 1e-12)
        sims = [np.dot(obs_norm, emb / (np.linalg.norm(emb) + 1e-12)) for emb in env.item_embeddings]
        action = env.item_embeddings[int(np.argmax(sims))]
        obs, r, terminated, truncated, _ = env.step(action)
        total += r
        done = terminated or truncated
    cosine_rewards.append(total)
cosine_rewards = np.array(cosine_rewards)

# print summary
def summary(name, arr):
    print(f"{name}: mean={arr.mean():.3f}, std={arr.std():.3f}, median={np.median(arr):.3f}")
summary("PPO_det", ppo_det)
summary("PPO_sto", ppo_sto)
summary("Random", random_rewards)
summary("Cosine", cosine_rewards)

# plot distributions
plt.figure(figsize=(10,6))
plt.hist(random_rewards, bins=50, alpha=0.4, label="Random")
plt.hist(cosine_rewards, bins=50, alpha=0.4, label="Cosine")
plt.hist(ppo_det, bins=50, alpha=0.6, label="PPO_det")
plt.hist(ppo_sto, bins=50, alpha=0.6, label="PPO_sto")
plt.legend()
plt.title("Reward distributions")
plt.xlabel("Episode total reward")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig("./training_output_continuous/eval_reward_distributions.png")
print("Saved plot to ./training_output_continuous/eval_reward_distributions.png")
