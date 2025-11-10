# train_ppo_user_sim_db_continuous.py
import os
import numpy as np
from sqlmodel import Session, create_engine, select
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor
from stable_baselines3.common.monitor import Monitor
import matplotlib.pyplot as plt
from reading_rec_env import ReadingRecEnvContinuous
from app.services.item_embeddings import create_item_embeddings, get_item_embedding_by_reading_id
from app.models import Reading

# ---------------------------
# Parameters
# ---------------------------
OUTPUT_DIR = "./training_output_continuous"
os.makedirs(OUTPUT_DIR, exist_ok=True)
MODEL_PATH = os.path.join(OUTPUT_DIR, "ppo_user_sim_continuous.zip")
PLOT_PATH = os.path.join(OUTPUT_DIR, "ppo_eval_rewards_continuous.png")
REWARDS_NPY = os.path.join(OUTPUT_DIR, "ppo_eval_rewards_continuous.npy")

TOTAL_TIMESTEPS = 20000
N_ENVS = 4
EVAL_EPISODES = 100

# ---------------------------
# Load embeddings from database
# ---------------------------
engine = create_engine("sqlite:///database.db")

with Session(engine) as session:
    # Make sure embeddings exist
    create_item_embeddings(session)

    # Query all reading IDs
    reading_ids = session.exec(select(Reading.id)).all()
    reading_embeddings = []

    for rid in reading_ids:
        vec = get_item_embedding_by_reading_id(session, rid)
        if vec is not None:
            reading_embeddings.append(vec)
        else:
            print(f"Warning: No embedding for reading id {rid}")

    reading_embeddings = np.array(reading_embeddings, dtype=np.float32)
    print("Loaded embeddings from DB:", reading_embeddings.shape)

# ---------------------------
# Make vectorized environment
# ---------------------------
def make_env():
    def _init():
        env = ReadingRecEnvContinuous(
            reading_embeddings,
            max_steps=50,
            noise_scale=0.05,
            discount_factor=0.5
        )
        return Monitor(env)
    return _init

vec_env = DummyVecEnv([make_env() for _ in range(N_ENVS)])
vec_env = VecMonitor(vec_env)

# ---------------------------
# Train PPO
# ---------------------------
model = PPO("MlpPolicy", vec_env, verbose=1)  # action space continuous nên vẫn dùng MlpPolicy
print("Start learning...")
model.learn(total_timesteps=TOTAL_TIMESTEPS)
model.save(MODEL_PATH)
print("Saved model to", MODEL_PATH)

# ---------------------------
# Evaluate
# ---------------------------
eval_env = ReadingRecEnvContinuous(
    reading_embeddings,
    max_steps=50,
    noise_scale=0.05,
    discount_factor=0.5
)
episode_rewards = []

for _ in range(EVAL_EPISODES):
    obs, _ = eval_env.reset()
    total = 0.0
    for _ in range(500):
        # model.predict trả về vector embedding trực tiếp
        action, _ = model.predict(obs, deterministic=True)
        # obs mới = user_state, action trực tiếp là vector embedding
        obs, r, terminated, truncated, _ = eval_env.step(action)
        total += r
        if terminated or truncated:
            break
    episode_rewards.append(total)

np.save(REWARDS_NPY, np.array(episode_rewards))
print("Saved eval rewards to", REWARDS_NPY)

# ---------------------------
# Plot rewards
# ---------------------------
plt.figure(figsize=(9, 4))
plt.plot(episode_rewards)
if len(episode_rewards) >= 5:
    ma = np.convolve(episode_rewards, np.ones(5)/5, mode='valid')
    plt.plot(range(4, 4 + len(ma)), ma)
plt.title("PPO evaluation rewards per episode (continuous action)")
plt.xlabel("Episode")
plt.ylabel("Total reward")
plt.tight_layout()
plt.savefig(PLOT_PATH)
print("Saved reward plot to", PLOT_PATH)
print("Done.")
