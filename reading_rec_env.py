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
    "click": 0.5,
    "submit": 0.8,
    "like": 1.0,
}

POSSIBLE_EVENTS = ["dislike", "skip", "view", "click", "submit", "like"]

def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


class ReadingRecEnv(gym.Env):
    """
    Môi trường rất đơn giản:
    - reset(): sample user_state từ reading_embeddings + small noise
    - step(action): lấy embedding của action, tính cosine sim với user_state,
      chuyển sim -> xác suất cho 6 tổ hợp, sample 1 tổ hợp, compute reward.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        reading_embeddings: np.ndarray,
        max_steps: int = 50,
        noise_scale: float = 0.05,
        discount_factor: float = 0.5
    ):
        assert isinstance(reading_embeddings, np.ndarray) and reading_embeddings.ndim == 2
        self.reading_embeddings = reading_embeddings.astype(np.float32)
        self.num_items, self.emb_dim = self.reading_embeddings.shape

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
        norms = np.linalg.norm(self.reading_embeddings, axis=1, keepdims=True) + 1e-12
        self.emb_normed = self.reading_embeddings / norms

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.step_count = 0
        self.history = []

        # sample an index and set user_state = reading_embedding + small noise
        idx = int(self.rng.integers(0, self.num_items))
        base = self.reading_embeddings[idx]
        noise = self.rng.normal(0, self.noise_scale, size=self.emb_dim).astype(np.float32)
        self.user_state = (base + noise).astype(np.float32)
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
        item_emb = self.reading_embeddings[action]
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


class ReadingRecEnvContinuous(gym.Env):
    """
    Continuous action environment with N-recent items memory
    """
    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        reading_embeddings: np.ndarray,
        max_steps: int = 50,
        noise_scale: float = 0.05,
        discount_factor: float = 0.5,
        scale: float = 6.0,
        recent_N: int = 5,
        skip_prob_if_seen: float = 0.9
    ):
        assert isinstance(reading_embeddings, np.ndarray) and reading_embeddings.ndim == 2
        self.reading_embeddings = reading_embeddings.astype(np.float32)
        self.num_items, self.emb_dim = self.reading_embeddings.shape

        self.max_steps = max_steps
        self.noise_scale = noise_scale
        self.discount_factor = discount_factor
        self.scale = scale
        self.recent_N = recent_N
        self.skip_prob_if_seen = skip_prob_if_seen

        self.rng = np.random.default_rng()
        self.user_state = np.zeros(self.emb_dim, dtype=np.float32)
        self.step_count = 0
        self.history: List[Dict[str, Any]] = []

        self.recent_items: List[int] = []

        norms = np.linalg.norm(self.reading_embeddings, axis=1, keepdims=True) + 1e-12
        self.emb_normed = self.reading_embeddings / norms

        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(self.emb_dim,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(self.emb_dim,), dtype=np.float32)

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.step_count = 0
        self.history = []
        self.recent_items = []

        idx = int(self.rng.integers(0, self.num_items))
        base = self.reading_embeddings[idx]
        noise = self.rng.normal(0, self.noise_scale, size=self.emb_dim).astype(np.float32)
        self.user_state = (base + noise).astype(np.float32)
        if np.linalg.norm(self.user_state) == 0:
            self.user_state += 1e-6
        return self.user_state.copy(), {}

    def step(self, action: np.ndarray):
        self.step_count += 1

        # Normalize action
        a_norm = action / (np.linalg.norm(action) + 1e-12)

        # Find most similar item to the action
        sims = self.emb_normed @ a_norm
        idx = int(np.argmax(sims))
        item_emb = self.reading_embeddings[idx]
        item_emb_norm = self.emb_normed[idx]

        # Compute similarity between item and user_state
        user_norm = self.user_state / (np.linalg.norm(self.user_state) + 1e-12)
        sim = float(np.dot(user_norm, item_emb_norm))
        sim01 = (sim + 1.0) / 2.0

        # Decrease interest if item was recently seen
        if idx in self.recent_items:
            sim01 *= 0.7

        # Probabilistic event sampling
        logits = np.arange(len(POSSIBLE_EVENTS), dtype=float) * (sim01 - 0.85) * self.scale
        probs = _softmax(logits)
        chosen_idx = int(self.rng.choice(len(POSSIBLE_EVENTS), p=probs))
        chosen_event = POSSIBLE_EVENTS[chosen_idx]
        total_reward = float(REWARD_MAP[chosen_event])

        # Update recent_items
        self.recent_items.append(idx)
        if len(self.recent_items) > self.recent_N:
            self.recent_items.pop(0)

        # Weighted average update
        weights = np.array([0.9 ** (len(self.recent_items) - 1 - i) for i in range(len(self.recent_items))], dtype=np.float32)
        embeddings = np.array([self.reading_embeddings[i] for i in self.recent_items], dtype=np.float32)
        new_state = np.average(embeddings, axis=0, weights=weights)

        # Smooth update with discount_factor
        self.user_state = (1 - self.discount_factor) * self.user_state + self.discount_factor * new_state
        self.user_state /= (np.linalg.norm(self.user_state) + 1e-12)

        # Record
        self.history.append({
            "action_vector": action.copy(),
            "chosen_index": idx,
            "chosen_embedding": item_emb.copy(),
            "sim": sim,
            "sim01": sim01,
            "event": chosen_event,
            "reward": total_reward,
            "recent_items": self.recent_items.copy(),
            "probs": probs.tolist(),
        })

        terminated = (chosen_event == "like")
        truncated = self.step_count >= self.max_steps
        obs = self.user_state.copy()
        info = {"event": chosen_event, "sim": sim, "chosen_index": idx, "recent_items": self.recent_items.copy()}

        return obs, total_reward, bool(terminated), bool(truncated), info


    def render(self):
        if not self.history:
            print("No interactions yet.")
            return
        last = self.history[-1]
        print(f"Step {self.step_count} | chosen={last['chosen_index']} | sim={last['sim']:.3f} | event={last['event']} | r={last['reward']:.3f} | recent={last['recent_items']}")

    def get_history(self):
        return self.history