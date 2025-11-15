import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import List, Dict, Any, Optional

# ==============================================================
# CÁC HẰNG SỐ & HỖ TRỢ
# ==============================================================

POSSIBLE_EVENTS = ["dislike", "skip", "view", "submit", "like"]
EVENT_REWARD_MAP = {
    "dislike": -1.0,
    "skip": -0.25,
    "view": 0.1,
    "submit": 0.8,
    "like": 1.0,
}

def softmax(x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    x = x / temperature
    e = np.exp(x - np.max(x))
    return e / e.sum()


import numpy as np
from typing import List, Dict, Any

class Reader:
    """
    Người dùng (user simulator) - chỉ biết:
    - Lịch sử tương tác của mình
    - Item hiện tại (action)
    - Trạng thái sở thích nội tại (user_preference)
    """
    def __init__(
        self,
        emb_dim: int,
        max_recent: int = 5,
        noise_scale: float = 0.05,
        update_alpha: float = 0.2,
        rng: Optional[np.random.Generator] = None,
    ):
        self.emb_dim = emb_dim
        self.max_recent = max_recent
        self.noise_scale = noise_scale
        self.update_alpha = update_alpha
        self.rng = rng or np.random.default_rng()

        # Nội tại người dùng
        self.user_preference = np.zeros(emb_dim, dtype=np.float32)
        self.history: List[Dict[str, Any]] = []
        self.recent_embs: List[np.ndarray] = []
        self.recent_sim01: List[float] = []

    def reset(self, seed_item_emb: np.ndarray):
        """Khởi tạo sở thích từ 1 item ban đầu"""
        self.history = []
        self.recent_embs = []
        self.recent_sim01 = []
        noise = self.rng.normal(0, self.noise_scale, self.emb_dim).astype(np.float32)
        self.user_preference = seed_item_emb + noise
        return self.user_preference.copy()

    @staticmethod
    def cosine_sim(v1: np.ndarray, v2: np.ndarray) -> float:
        num = np.dot(v1, v2)
        den = np.sqrt(np.sum(v1**2)) * np.sqrt(np.sum(v2**2)) + 1e-12
        return float(num / den)

    @staticmethod
    def diversity(vectors: np.ndarray) -> float:
        if len(vectors) <= 1:
            return 1.0
        sims = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                sims.append(Reader.cosine_sim(vectors[i], vectors[j]))
        return max(0.0, 1.0 - np.mean(sims))

    @staticmethod
    def diversity_gain(existing: List[np.ndarray], new_vec: np.ndarray) -> float:
        if not existing:
            return 1.0
        d0 = Reader.diversity(np.array(existing))
        d1 = Reader.diversity(np.array(existing + [new_vec]))
        return d1 - d0

    def step(self, item_emb: np.ndarray) -> Dict[str, Any]:
        """
        Nhận item embedding → trả về reward + cập nhật nội tại
        """
        item_emb = np.asarray(item_emb, dtype=np.float32)

        # 1. Similarity với sở thích
        sim = Reader.cosine_sim(self.user_preference, item_emb)
        sim01 = (sim + 1.0) / 2.0

        # 2. Cập nhật recent
        self.recent_embs.append(item_emb)
        self.recent_sim01.append(sim01)
        if len(self.recent_embs) > self.max_recent:
            self.recent_embs.pop(0)
            self.recent_sim01.pop(0)

        # ----------- START USER SIMULATOR ---------------
        # 3. Tính hidden state: sum reward + diversity
        recent_rewards = [h["reward"] for h in self.history[-self.max_recent:]]
        sum_recent_reward = sum(recent_rewards) if recent_rewards else 0.0
        diversity = Reader.diversity(np.array(self.recent_embs))

        # 4. Logic ẩn: khi nào thưởng giống / khác?
        reward_high = sum_recent_reward >= 0.0
        reward_low = sum_recent_reward < 0.0
        div_low = diversity < 0.4
        div_high = diversity >= 0.6

        target_similar = reward_high or (reward_low and div_high)
        target_diverse = reward_low and div_low

        # 5. Tính dense score
        exploit_score = sim01
        explore_score = np.clip((Reader.diversity_gain(self.recent_embs[:-1], item_emb) + 1.0) / 2.0, 0.0, 1.0)

        if target_similar:
            dense_reward = exploit_score
        elif target_diverse:
            dense_reward = explore_score
        else:
            dense_reward = 0.5 * (exploit_score + explore_score)

        # 6. Sự kiện ngẫu nhiên (xác suất ẩn)
        base_logits = np.array([-10.0, -2.0, 0.0, 2.0, 4.0])
        bonus = 6.0 * dense_reward
        probs = np.exp(base_logits + bonus)
        probs /= probs.sum()
        event_idx = self.rng.choice(5, p=probs)
        event = ["dislike", "skip", "view", "submit", "like"][event_idx]

        # 7. Final reward
        total_reward = dense_reward
        if event == "like":
            total_reward += 1.0
        elif event == "dislike":
            total_reward -= 0.5

        # ----------- END USER SIMULATOR ---------------

        # 8. Cập nhật user_preference (residual)
        self.user_preference = Reader.update_user_preference(self.user_preference, item_emb, total_reward, self.update_alpha)

        # 9. Lưu lịch sử
        info = {
            "sim01": round(sim01, 3),
            "diversity": round(diversity, 3),
            "sum_reward": round(sum_recent_reward, 3),
            "dense_reward": round(dense_reward, 3),
            "event": event,
            "reward": float(total_reward),
            "probs": np.round(probs, 3).tolist(),
        }
        self.history.append(info)

        return info
    
    @staticmethod
    def update_user_preference(user_preference, item_emb, total_reward, update_alpha=0.2):
        """
        Cập nhật state người dùng theo hướng item_emb nhưng chỉ lấy phần residual
        (tức là phần thông tin 'mới' khác với user_preference hiện tại).
        """
        user_preference = user_preference.copy()

        # projection of item onto user_preference
        denom = np.sum(user_preference**2) + 1e-12
        coef = np.dot(user_preference, item_emb) / denom
        proj = coef * user_preference  # thành phần "đã biết"

        residual = item_emb - proj  # phần mới → học vào user_preference

        # update
        return user_preference + update_alpha * total_reward * residual
    
class ReadingRecEnvContinuous(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        item_database: np.ndarray,  # toàn bộ item embeddings
        max_steps: int = 50,
        max_recent: int = 5,
        seed: Optional[int] = None,
    ):
        super().__init__()
        self.item_db = np.asarray(item_database, dtype=np.float32)
        self.num_items, self.emb_dim = self.item_db.shape

        self.max_steps = max_steps
        self.max_recent = max_recent
        self.rng = np.random.default_rng(seed)

        # Tạo user
        self.reader = Reader(
            emb_dim=self.emb_dim,
            max_recent=max_recent,
            rng=self.rng,
        )

        # Action = 1 item embedding (liên tục)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(self.emb_dim,), dtype=np.float32)

        # Observation = user_preference + signals
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(self.emb_dim + 4,),  # user_preference + div + sum_r + avg_sim + mood
            dtype=np.float32
        )

        self.step_count = 0

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            self.reader.rng = self.rng

        self.step_count = 0

        # Chọn 1 item ngẫu nhiên làm điểm khởi đầu sở thích
        idx = self.rng.integers(0, self.num_items)
        seed_emb = self.item_db[idx]
        self.reader.reset(seed_emb)

        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        self.step_count += 1
        action = np.asarray(action, dtype=np.float32)

        # --- Gợi ý, tìm item gần nhất với action ---
        logits = self.item_db @ action
        probs = softmax(logits, temperature=0.1)
        item_idx = int(self.rng.choice(self.num_items, p=probs))
        suggested_item = self.item_db[item_idx]

        # --- User phản hồi ---
        user_response = self.reader.step(suggested_item)

        # --- Trả về ---
        terminated = user_response["event"] == "like"
        truncated = self.step_count >= self.max_steps

        recent_rewards = [h["reward"] for h in self.reader.history[-self.max_recent:]]
        return ReadingRecEnvContinuous.get_obs(
            self.reader.user_preference, 
            self.reader.recent_embs,
            recent_rewards,
            self.reader.recent_sim01), user_response["reward"], terminated, truncated, user_response

    @staticmethod
    def get_obs(user_preference, recent_embs, recent_rewards, recent_sim01s) -> np.ndarray:
        # Từ Reader
        div = Reader.diversity(np.array(recent_embs)) if len(recent_embs) > 1 else 1.0
        sum_r = sum(np.array(recent_rewards)) if len(recent_rewards) > 0 else 0.0
        avg_sim = np.mean(np.array(recent_sim01s)) if len(recent_sim01s) > 0 else 0.5
        mood = 0.5 * (1.0 + np.tanh(sum_r))

        return np.concatenate([
            user_preference,
            np.array([div, sum_r, avg_sim, mood], dtype=np.float32)
        ])

    def render(self):
        if not self.reader.history:
            print("No interaction.")
            return
        last = self.reader.history[-1]
        print(
            f"[Step {self.step_count}] "
            f"Sim:{last['sim01']:.2f} Div:{last['diversity']:.2f} "
            f"SumR:{last['sum_reward']:.2f} → {last['event']} | R:{last['reward']:.2f}"
        )