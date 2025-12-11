# ------------------ 1) Imports ------------------
import random
import numpy as np
import pandas as pd
from sqlmodel import SQLModel, Field, select, Session
from sentence_transformers import SentenceTransformer
import gym
from gym import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from app.database import engine
from app.models import FeedBack, User, UserTopicLink, Topic
from app.services.generate_question import embedder

# ------------------ 4) Load data từ DB ------------------
with Session(engine) as session:
    df_feedback = pd.DataFrame([f.model_dump() for f in session.exec(select(FeedBack)).all()])
    df_user = pd.DataFrame([u.model_dump() for u in session.exec(select(User)).all()])
    df_topic = pd.DataFrame([t.model_dump() for t in session.exec(select(Topic)).all()])
    df_usertopiclink = pd.DataFrame([l.model_dump() for l in session.exec(select(UserTopicLink)).all()])

# ------------------ 5) Precompute embeddings ------------------
MAX_CAND = 8

# --- user embeddings ---
def user_to_text(row):
    user_topics = df_usertopiclink[df_usertopiclink['user_id'] == row['id']]['topic_id'].tolist()
    topic_names = df_topic[df_topic['id'].isin(user_topics)]['name'].tolist()
    txt = f"Goal: {row['goal_type']}, Age group: {row['age_group']}, Topics: {' '.join(topic_names)}"
    return txt

df_user['user_text'] = df_user.apply(user_to_text, axis=1)
user_embs = np.array(embedder.encode(df_user['user_text'].tolist(), convert_to_numpy=True))
user_id2idx = {uid: idx for idx, uid in enumerate(df_user['id'].tolist())}

# --- passage embeddings ---
passage_texts = df_feedback['reading_text'].unique().tolist()
passage_embs = np.array(embedder.encode(passage_texts, convert_to_numpy=True))
passage2idx = {p: i for i, p in enumerate(passage_texts)}

# --- question embeddings ---
question_texts = df_feedback['question_text'].unique().tolist()
question_embs = np.array(embedder.encode(question_texts, convert_to_numpy=True))
q2idx = {q: i for i, q in enumerate(question_texts)}

# --- passage -> candidate questions ---
passage2qidxs = {}
for _, row in df_feedback.iterrows():
    p = row['reading_text']
    q_idx = q2idx[row['question_text']]
    passage2qidxs.setdefault(p, []).append(q_idx)

# ------------------ 6) Build episodic dataset ------------------
dataset_env = []

for _, hist in df_feedback.iterrows():
    # Map username -> user_id
    user_row = df_user[df_user['username'] == hist['user_name']].iloc[0]
    user_idx = user_id2idx[user_row['id']]

    passage = hist["reading_text"]
    chosen_question = hist["question_text"]
    score_value = float(hist["score"])
    passage_idx = passage2idx[passage]

    # Candidate questions
    candidates = passage2qidxs[passage].copy()
    if len(candidates) > MAX_CAND:
        candidates = random.sample(candidates, MAX_CAND)
    else:
        while len(candidates) < MAX_CAND:
            random_q = random.randrange(len(question_texts))
            if random_q not in candidates:
                candidates.append(random_q)
    random.shuffle(candidates)

    # Logged outcomes
    logged_outcomes = {}
    chosen_q_idx = q2idx.get(chosen_question, None)
    if chosen_q_idx is not None and chosen_q_idx in candidates:
        pos = candidates.index(chosen_q_idx)
        logged_outcomes[pos] = score_value

    dataset_env.append({
        "user_emb": user_embs[user_idx],
        "passage_emb": passage_embs[passage_idx],
        "candidate_idxs": candidates,
        "logged_outcomes": logged_outcomes
    })

print("Built dataset_env with", len(dataset_env), "episodes")

# ------------------ 7) Define Gym environment ------------------
class QRecommendEnv(gym.Env):
    def __init__(self, dataset):
        super().__init__()
        self.dataset = dataset
        self.max_cand = MAX_CAND
        self.ptr = 0

        obs_dim = (
            user_embs.shape[1] +
            passage_embs.shape[1] +
            MAX_CAND * question_embs.shape[1]
        )
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Discrete(MAX_CAND)

    def reset(self):
        self.ptr = random.randrange(len(self.dataset))
        rec = self.dataset[self.ptr]
        self.current = rec
        user = rec["user_emb"]
        passage = rec["passage_emb"]
        cand_embs = question_embs[rec["candidate_idxs"]]
        obs = np.concatenate([user, passage, cand_embs.flatten()]).astype(np.float32)
        return obs

    def step(self, action):
        rec = self.current
        if action in rec["logged_outcomes"]:
            reward = float(rec["logged_outcomes"][action])
        else:
            up = rec["user_emb"] + rec["passage_emb"]
            qv = question_embs[rec["candidate_idxs"][action]]
            cos = float(np.dot(up, qv) / ((np.linalg.norm(up)+1e-8)*(np.linalg.norm(qv)+1e-8)))
            reward = 0.2 if cos > 0.6 else (0.05 if cos > 0.4 else -0.05)

        done = True
        info = {"score_if_logged": rec["logged_outcomes"].get(action, None)}
        next_obs = np.zeros(self.observation_space.shape, dtype=np.float32)
        return next_obs, reward, done, info

# ------------------ 8) Train PPO ------------------
env = QRecommendEnv(dataset_env)
vec_env = DummyVecEnv([lambda: env])

model = PPO("MlpPolicy", vec_env, verbose=1, batch_size=16, n_steps=64, learning_rate=2.5e-4)
model.learn(total_timesteps=10000)

model.save("ai_model/ppo_question_rec2")