import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import List, Dict, Any, Optional
from app.config import settings
from np_utils import cosine_sim, top_k_l2_nearest_idx


EVENT_REWARD_MAP = {
    "dislike": -1.0,
    "skip": -0.25,
    "view": 0.1,
    "submit": 0.8,
    "like": 1.0,
}

POSSIBLE_EVENTS = list(EVENT_REWARD_MAP.keys())

class Reader:
    """
    Người dùng (user simulator) - chỉ biết:
    - Lịch sử tương tác của mình
    - Item hiện tại (action)
    - Trạng thái sở thích nội tại (_user_preference)
    """
    def __init__(
        self,
        emb_dim: int,
        max_recent: int = settings.recent_history_size,
        noise_scale: float = 0.05,
        boredom_rate = 0.3,
        rng: Optional[np.random.Generator] = None,
    ):
        self.emb_dim = emb_dim
        self.max_recent = max_recent
        self.noise_scale = noise_scale
        self.boredom_rate = boredom_rate
        self.rng = rng or np.random.default_rng()
        self.actions = POSSIBLE_EVENTS
        self.rewards = list(EVENT_REWARD_MAP.values())

        # Độ nhạy của từng action với satisfaction
        # Càng âm → càng dễ xảy ra khi satisfaction âm
        # Càng dương → càng dễ khi satisfaction dương
        self.sensitivity = np.array([-8.0, -5.0, 0.5, 2.0, 1.5])

        # Độ hiếm tự nhiên (càng nhỏ càng hiếm)
        self.rarity = np.array([0.5, 2, 2, 1, 0.5])  # dislike & like hiếm

        # Nội tại người dùng
        self._user_preference = np.zeros(emb_dim, dtype=np.float32)
        self.recent_embs: List[np.ndarray] = []
        self.recent_rewards: List[float] = []
        self.recent_relevants: List[float] = []

    def reset(self, seed_item_emb: np.ndarray):
        """Khởi tạo sở thích từ 1 item ban đầu"""
        self.recent_embs = []
        self.recent_rewards = []
        self.recent_relevants = []
        
        noise = self.rng.normal(0, self.noise_scale, self.emb_dim).astype(np.float32)
        self._user_preference = seed_item_emb + noise

    @staticmethod
    def diversity(vectors: np.ndarray) -> float:
        if len(vectors) <= 1:
            return 1.0
        sims = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                sims.append(cosine_sim(vectors[i], vectors[j]))
        return max(0.0, 1.0 - np.mean(sims))

    @staticmethod
    def diversity_gain(existing: List[np.ndarray], new_vec: np.ndarray) -> float:
        if not existing:
            return 1.0
        d0 = Reader.diversity(np.array(existing))
        d1 = Reader.diversity(np.array(existing + [new_vec]))
        return d1 - d0

    def step(self, item_emb: np.ndarray, update_state: bool = True) -> Dict[str, Any]:
        """
        Nhận trực tiếp item embedding (no normalized) → trả về reward + cập nhật nội tại ẩn
        """
        item_emb = np.asarray(item_emb, dtype=np.float32)
        
        # ----------- START USER SIMULATOR ---------------
        # Khi biết được mong muốn của người dùng, điểm sẽ cao nếu item thỏa mãn và thấp nếu ít thỏa mãn
        exploit_score = cosine_sim(self._user_preference, item_emb)

        # diversity is in range [0, 2]
        gain = Reader.diversity_gain(self.recent_embs, item_emb) # [-2, 2]
        explore_score = gain / 2.0

        satisfaction = 0.9 * exploit_score + 0.1 * explore_score
        if not -1.0 <= satisfaction <= 1.0:
            print(f"WARNING: satisfaction:{satisfaction}, cliped")
            satisfaction = np.clip(satisfaction, -1.0, 1.0)

        # Mô phỏng user đưa ra phản hồi dựa trên satisfaction của item được gợi ý
        # satisfaction thể hiện item này hợp với người dùng như thế nào một cách tổng thể
        # satisfaction là những gì thuộc về  determistic, hành vi người dùng có thể  'đoán được'
        # Nhưng đối với real user, họ có thể  đột nhiên thấy chán và cho điểm thấp với cái 'đoán được' đó với cùng trạng thái
        # Yếu đố  không thể đoán trước được này cần được định nghĩa bằng một con số  thể hiện sự nhanh chán của người dùng
        # Người dùng càng nhanh chán thì những hành vi cho điểm bất ngờ của họ sẽ nhiều hơn.
        # Những sự kiện mà người dùng có thể đưa ra cũng có những 'độ hiếm' khác nhau.
        # Ví dụ hầu hết thời gian người dùng sẽ cho các hành động skip, view, và đôi khi submit, và hiếm khi like, dislike.
        # Cuối cùng phải quy về việc chọn hành động, satisfaction chỉ ảnh hưởng việc chọn hành động, không đóng góp và reward cuối cùng.
        
        # Tính logits: bias (hiếm) + ảnh hưởng từ satisfaction
        logits = self.rarity + satisfaction * self.sensitivity

        # Softmax
        probs = np.exp(logits - np.max(logits))
        probs /= probs.sum()

        # Chọn action
        idx = self.rng.choice(len(self.actions), p=probs)
        # ----------- END USER SIMULATOR ---------------

        # Reward CHỈ từ hành động
        reward = self.rewards[idx]
        event = self.actions[idx]

        # Chán một cách ngẫu nhiên
        # Chọn hành động tiêu cực bất kể yếu tố gì
        is_bored = self.rng.random() < self.boredom_rate
        if is_bored:
            neg_events = [e for e in POSSIBLE_EVENTS if EVENT_REWARD_MAP[e] < 0]
            neg_indices = [POSSIBLE_EVENTS.index(e) for e in neg_events]

            # Corresponding rarities
            neg_rarity = self.rarity[neg_indices]
            prob = neg_rarity / neg_rarity.sum()

            # Pick a random one
            event = np.random.choice(neg_events, p=prob)
            reward = EVENT_REWARD_MAP[event]
            
        if update_state:
            # Cập nhật _user_preference (residual) dựa trên item gợi ý và reward nhận được
            self._update_user_preference(item_emb, reward)

            # Cập nhật recent
            self.recent_embs.append(item_emb)
            self.recent_rewards.append(reward)
            self.recent_relevants.append(exploit_score)
            if len(self.recent_embs) > self.max_recent:
                self.recent_embs.pop(0)
                self.recent_rewards.pop(0)
                self.recent_relevants.pop(0)

        sum_recent_reward = sum(self.recent_rewards) if self.recent_rewards else 0.0
        updated_diversity = Reader.diversity(np.vstack(self.recent_embs + [item_emb]))
        info = {
            "relevant": round(exploit_score, 3),
            "updated_diversity": round(updated_diversity, 3),
            "sum_reward": round(sum_recent_reward, 3),
            "satisfaction": round(satisfaction, 3),
            "event": event,
            "reward": float(reward),
            "is_bored": is_bored
        }
        return info
    
    def _update_user_preference(self, item_emb, reward):
        """
        Cập nhật state người dùng theo hướng item_emb nhưng chỉ lấy phần residual
        (tức là phần thông tin 'mới' khác với _user_preference hiện tại).
        """
        # projection of item onto _user_preference
        denom = np.sum(self._user_preference**2) + 1e-12
        coef = np.dot(self._user_preference, item_emb) / denom
        proj = coef * self._user_preference  # thành phần "đã biết"
        residual = item_emb - proj  # phần mới sẽ học vào _user_preference
        self._user_preference = self._user_preference + self.boredom_rate * reward * residual
    
    
class ReadingRecEnvContinuous(gym.Env):
    def __init__(
        self,
        item_database: np.ndarray,  # toàn bộ item embeddings
        max_steps: int = 50,
        max_recent: int = settings.recent_history_size,
        seed: Optional[int] = None,
    ):
        super().__init__()
        self.item_db = np.asarray(item_database, dtype=np.float32)
        self.num_items, self.emb_dim = self.item_db.shape
        self.item_norms = np.linalg.norm(self.item_db, axis=1)

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
        self.action_space = spaces.Box(
            low=self.item_db.min(axis=0), 
            high=self.item_db.max(axis=0), 
            shape=(self.emb_dim,), 
            dtype=np.float32
        )

        # Observation = mean_recent_item_embs + signals
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(self.emb_dim + 2,),  # mean_recent_item_embs + div + mood
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

        # Reset user
        self.reader.reset(seed_emb)
        return ReadingRecEnvContinuous.get_obs(self.emb_dim, [], []), {}

    def step(self, action: np.ndarray):
        """ action with values from normalized item space, comes directly from agent. """
        self.step_count += 1
        action = np.asarray(action, dtype=np.float32)

        if np.linalg.norm(action) == 0:
            # fallback: random item
            item_idx = int(self.rng.integers(self.num_items))
        else:
            item_idx = int(top_k_l2_nearest_idx(self.item_db, action, k=1)[0])

        suggested_item = self.item_db[item_idx]

        # --- User phản hồi ---
        user_response = self.reader.step(suggested_item)

        # --- Trả về ---
        terminated = False # user_response["event"] == "like"
        truncated = self.step_count >= self.max_steps

        return ReadingRecEnvContinuous.get_obs(
            self.emb_dim,
            self.reader.recent_embs,
            self.reader.recent_rewards), user_response["reward"], terminated, truncated, user_response

    @staticmethod
    def get_obs(emb_dim, recent_embs, recent_rewards) -> np.ndarray:
        # Từ Reader
        if recent_embs:
            arr = np.asarray(recent_embs, dtype=np.float32)
            mean_recent_embs = np.mean(arr, axis=0).astype(np.float32)
            div = Reader.diversity(arr) if len(arr) > 1 else 1.0
        else:
            mean_recent_embs = np.zeros(emb_dim, dtype=np.float32)
            div = 1.0

        sum_r = sum(np.array(recent_rewards)) if recent_rewards else 0.0
        mood = np.tanh(sum_r)

        return np.concatenate([
            mean_recent_embs,
            np.array([div, mood], dtype=np.float32)
        ])
