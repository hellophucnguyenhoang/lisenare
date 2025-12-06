from stable_baselines3 import PPO
from reading_env import ReadingRecEnvContinuous
from sqlmodel import Session, create_engine
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from app.services.item_embeddings import get_all_embeddings


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

model = PPO("MlpPolicy", env)
print(model.policy)