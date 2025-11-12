import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import List, Dict, Any, Optional

SEQUENCES = [
    ["skip"],
    ["click", "skip"],
    ["view", "skip"],
    ["view", "click", "skip"],
    ["view", "click", "submit", "skip"],
    ["view", "click", "submit", "like"],
]

REWARD_MAP = {
    "dislike": -1.0,
    "skip": -0.25,
    "view": 0.1,
    "submit": 0.8,
    "like": 1.0,
}

# Cách sắp xếp này không phải ngẫu nhiên, xem cách tính xác suất từ cosine sim trong step()
POSSIBLE_EVENTS = ["dislike", "skip", "view", "submit", "like"]

def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()

def projection_novelty_update_user_state(s, a, r, alpha, recent_embs):
    a_norm = normalize(a)
    proj = np.dot(s, a_norm) * (a_norm ** 2)
    novelty = compute_novelty(a_norm, recent_embs)
    s_new = s + alpha * novelty * (r * 0.7 * proj + r * 0.3 * a)
    return normalize(s_new)

def projection_update_user_state(s, a, r, alpha):
    a_norm = normalize(a)
    proj = np.dot(s, a_norm) * (a_norm ** 2)
    s_new = s + alpha * (r * 0.7 * proj + r * 0.3 * a)
    return normalize(s_new)

class ReadingRecEnv(gym.Env):
    """
    Môi trường rất đơn giản:
    - reset(): sample user_state từ item_embeddings + small noise
    - step(action): lấy embedding của action, tính cosine sim với user_state,
      chuyển sim -> xác suất cho 6 tổ hợp, sample 1 tổ hợp, compute reward.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        item_embeddings: np.ndarray,
        max_steps: int = 100,
        noise_scale: float = 0.05,
        discount_factor: float = 0.5
    ):
        assert isinstance(item_embeddings, np.ndarray) and item_embeddings.ndim == 2
        self.item_embeddings = item_embeddings.astype(np.float32)
        self.num_items, self.emb_dim = self.item_embeddings.shape

        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(self.emb_dim,), dtype=np.float32)
        self.action_space = spaces.Discrete(self.num_items)

        self.max_steps = max_steps
        self.noise_scale = noise_scale
        self.discount_factor = discount_factor

        # RNG
        self.rng = np.random.default_rng()

        # internal
        self.user_state = np.zeros(self.emb_dim, dtype=np.float32)
        self.step_count = 0
        self.history: List[Dict[str, Any]] = []

        # normalized embeddings to compute cosine fast
        norms = np.linalg.norm(self.item_embeddings, axis=1, keepdims=True) + 1e-12
        self.emb_normed = self.item_embeddings / norms

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.step_count = 0
        self.history = []

        # sample an index and set user_state = reading_embedding + small noise
        idx = int(self.rng.integers(0, self.num_items))
        base = self.item_embeddings[idx]
        noise = self.rng.normal(0, self.noise_scale, size=self.emb_dim).astype(np.float32)
        self.user_state = (base + noise).astype(np.float32)
        self.user_state /= np.linalg.norm(self.user_state) + 1e-12

        # ensure non-zero
        if np.linalg.norm(self.user_state) == 0:
            self.user_state += 1e-6

        return self.user_state.copy(), {}

    def _cosine_sim(self, a: np.ndarray, b_normed: np.ndarray) -> float:
        # b_normed is normalized rows; a not necessarily normalized
        a_norm = a / (np.linalg.norm(a) + 1e-12)
        sim = float(b_normed @ a_norm) if b_normed.ndim == 1 else float(np.dot(b_normed, a_norm))
        return sim  # in [-1,1] if b_normed normalized

    def step(self, action: int):
        self.step_count += 1
        assert 0 <= action < self.num_items

        # item embedding (normalized)
        item_emb = self.item_embeddings[action]
        item_emb_norm = item_emb / (np.linalg.norm(item_emb) + 1e-12)

        # cosine similarity in [-1, 1]
        sim = float(np.dot(item_emb_norm, (self.user_state / (np.linalg.norm(self.user_state) + 1e-12))))
        # map to [0,1]
        sim01 = (sim + 1.0) / 2.0

        # simple mapping -> logits for sequences
        # complexity indices 0..5 (higher -> more engaged sequence)
        complexities = np.arange(len(SEQUENCES), dtype=float)  # [0,1,2,3,4,5]
        # scale controls separation; fixed constant so no tuning needed usually
        scale = 6.0
        # center sim at 0.5 so sim01<0.5 favors low-complexity (skip), sim01>0.5 favors high-complexity
        logits = complexities * (sim01 - 0.85) * scale
        probs = _softmax(logits)

        # sample one sequence
        seq_idx = int(self.rng.choice(len(SEQUENCES), p=probs))
        seq = SEQUENCES[seq_idx]

        # compute reward = sum of event rewards
        total_reward = float(sum(REWARD_MAP.get(ev, 0.0) for ev in seq))

        self.user_state = (
            (1 - self.discount_factor) * self.user_state
            + self.discount_factor * item_emb
        )

        # save to history: include embedding and index as you requested
        self.history.append({
            "action_index": int(action),
            "action_embedding": item_emb.copy(),
            "sim": float(sim),
            "sim01": float(sim01),
            "sequence": seq,
            "reward": total_reward,
            "probs": probs.tolist(),
            "seq_idx": seq_idx
        })

        # terminated if 'like' present
        terminated = ("like" in seq)
        truncated = self.step_count >= self.max_steps

        obs = self.user_state.copy()
        info = {"sequence": seq, "probs": probs.tolist(), "sim": sim}

        return obs, total_reward, bool(terminated), bool(truncated), info

    def render(self):
        if not self.history:
            print("No interactions yet.")
            return
        last = self.history[-1]
        print(f"Step {self.step_count} | action={last['action_index']} | sim={last['sim']:.3f} | seq={last['sequence']} | r={last['reward']:.3f}")

    # helper to inspect history
    def get_history(self) -> List[Dict[str, Any]]:
        return self.history


def normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    return v / (np.linalg.norm(v) + eps)

def cosine_similarity(v1: np.ndarray, v2: np.ndarray, eps: float = 1e-12) -> float:
    v1n, v2n = normalize(v1, eps), normalize(v2, eps)
    return float(np.dot(v1n, v2n))

def mean_cosine_similarity(v: np.ndarray, M: np.ndarray, eps: float = 1e-12) -> float:
    # M: (n, d), v: (d,)
    v_norm = normalize(v, eps)
    M_norm = M / (np.linalg.norm(M, axis=1, keepdims=True) + eps)
    sims = M_norm @ v_norm
    return float(np.mean(sims))

def compute_novelty(v: np.ndarray, recent: np.ndarray) -> float:
    """Return novelty in [0,1]: 1 means fully new, 0 means identical to history"""
    if len(recent) == 0:
        return 1.0
    return 1.0 - mean_cosine_similarity(v, recent)

class ReadingRecEnvContinuous(gym.Env):
    """
    Continuous action environment with N-recent items memory
    """
    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        item_embeddings: np.ndarray,
        max_steps: int = 100,
        noise_scale: float = 0.05,
        project_out_scale: float = 0.2,
        prob_scale: float = 6.0,
        max_recent: int = 5,
        user_conservative: float = 0.5
    ):
        assert isinstance(item_embeddings, np.ndarray) and item_embeddings.ndim == 2
        self.item_embeddings = item_embeddings.astype(np.float32)
        self.num_items, self.emb_dim = self.item_embeddings.shape

        self.max_steps = max_steps
        self.noise_scale = noise_scale
        self.project_out_scale = project_out_scale
        self.prob_scale = prob_scale
        self.max_recent = max_recent
        self.user_conservative = user_conservative

        self.rng = np.random.default_rng()
        self.user_state = np.zeros(self.emb_dim, dtype=np.float32)
        self.step_count = 0
        self.history: List[Dict[str, Any]] = []

        self.recent_items: List[int] = []

        norms = np.linalg.norm(self.item_embeddings, axis=1, keepdims=True) + 1e-12
        self.emb_normed = self.item_embeddings / norms

        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(self.emb_dim + 2,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(self.emb_dim,), dtype=np.float32)

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.step_count = 0
        self.history = []
        self.recent_items = []

        idx = int(self.rng.integers(0, self.num_items))
        # print(f"Reset: sampled index {idx}")
        base = self.item_embeddings[idx]
        noise = self.rng.normal(0, self.noise_scale, size=self.emb_dim).astype(np.float32)
        self.user_state = (base + noise).astype(np.float32)
        if np.linalg.norm(self.user_state) == 0:
            self.user_state += 1e-6
        return self.get_state_vector(), {}

    def step(self, action: np.ndarray):
        self.step_count += 1

        # Normalize action
        a_norm = normalize(action)

        # Find most similar item to the action
        sims = self.emb_normed @ a_norm
        item_idx = int(np.argmax(sims))
        item_emb = self.item_embeddings[item_idx]
        item_emb_norm = self.emb_normed[item_idx]

        # Compute similarity between item and user_state
        sim = cosine_similarity(self.user_state, item_emb)
        sim01 = (sim + 1.0) / 2.0

        novelty = compute_novelty(item_emb_norm, self.emb_normed[self.recent_items])

        # --- Combine similarity & novelty ---
        reward_base = self.user_conservative * sim01 + (1 - self.user_conservative) * novelty

        # Probabilistic event sampling
        event_logits = np.arange(len(POSSIBLE_EVENTS), dtype=float) * (reward_base - 0.8) * self.prob_scale
        event_probs = _softmax(event_logits)
        event_idx = int(self.rng.choice(len(POSSIBLE_EVENTS), p=event_probs))
        chosen_event = POSSIBLE_EVENTS[event_idx]
        total_reward = float(REWARD_MAP[chosen_event])

        # Update recent_items
        self.recent_items.append(item_idx)
        if len(self.recent_items) > self.max_recent:
            self.recent_items.pop(0)

        self.user_state = projection_update_user_state(
            self.user_state, 
            self.item_embeddings[item_idx], 
            r=total_reward, 
            alpha=self.project_out_scale
        )

        # Record
        self.history.append({
            "action_vector": action.copy(),
            "chosen_idx": item_idx,
            "chosen_emb": item_emb.copy(),
            "sim": sim,
            "sim01": sim01,
            "event": chosen_event,
            "reward": total_reward,
            "recent_items": self.recent_items.copy(),
            "probs": event_probs.tolist(),
        })

        terminated = (chosen_event == "like")
        truncated = self.step_count >= self.max_steps
        obs = self.get_state_vector()
        info = {"chsn_idx": item_idx, "evt": chosen_event, "sim01": float(np.round(sim01, 2)), "nov": float(np.round(novelty, 2)), "rcet_items": self.recent_items.copy(), "probs": np.round(event_probs, 2).tolist()}

        return obs, total_reward, bool(terminated), bool(truncated), info

    def get_state_vector(self):
        # 1️⃣ base: hướng sở thích (như hiện tại)
        s_pref = normalize(self.user_state)

        # 2️⃣ diversity: mức độ giống nhau giữa các item gần đây
        if len(self.recent_items) > 1:
            recent_embs = self.emb_normed[self.recent_items]
            sims = np.tril(recent_embs @ recent_embs.T, -1)
            sims = sims[sims != 0]
            diversity = 1.0 - np.mean(sims)
        else:
            diversity = 1.0

        # 3️⃣ reward trend: trung bình reward gần nhất
        if len(self.history) > 0:
            recent_rewards = [h["reward"] for h in self.history[-self.max_recent:]]
            reward_trend = np.mean(recent_rewards)
        else:
            reward_trend = 0.0

        # 4️⃣ gộp lại thành vector
        return np.concatenate([
            s_pref,                           # (d,)
            np.array([diversity, reward_trend], dtype=np.float32)  # (2,)
        ]).astype(np.float32)

    def render(self):
        if not self.history:
            print("No interactions yet.")
            return
        last = self.history[-1]
        print(f"Step {self.step_count} | chosen={last['chosen_index']} | sim={last['sim']:.3f} | event={last['event']} | r={last['reward']:.3f} | recent={last['recent_items']}")

    def get_history(self):
        return self.history