import json
import pickle

import numpy as np
from numpy.typing import NDArray

from app.config import settings
from utils.np_utils import cosine_sim


class SharedLinUCBModel:
    def __init__(self, n_features: int, alpha: float = 1.0):
        self.n_features = n_features
        self.alpha = alpha
        self.A = np.eye(n_features)
        self.b = np.zeros(n_features)

    def save(self, filepath: str):
        """Saves the model parameters to a .npz file."""
        np.savez(
            filepath,
            A=self.A,
            b=self.b,
            alpha=np.array([self.alpha]),
            n_features=np.array([self.n_features]),
        )

    @classmethod
    def load(cls, filepath: str):
        """Loads a model from a .npz file and returns a new instance."""
        data = np.load(filepath)
        # Initialize instance with saved scalars
        instance = cls(
            n_features=int(data["n_features"][0]),
            alpha=float(data["alpha"][0]),
        )
        # Restore matrices
        instance.A = data["A"]
        instance.b = data["b"]
        return instance

    def select_arm(
        self, arm_features: NDArray, top_k: int = 1
    ) -> int | list[int]:
        """
        Returns the indices of the top_k arms with the highest UCB scores.\n
        arm_features: shape (n_arms, n_features)\n
        Each row is the feature vector x for one arm
        """
        A_inv = np.linalg.inv(self.A)
        theta = A_inv @ self.b

        p_values = np.zeros(len(arm_features))
        mean_rewards = arm_features @ theta
        uncertainties = np.sqrt(
            np.sum((arm_features @ A_inv) * arm_features, axis=1)
        )
        p_values = mean_rewards + self.alpha * uncertainties
        top_indices = np.argsort(p_values)[-top_k:][::-1]
        top_indices = top_indices.tolist()
        if len(top_indices) == 1:
            return top_indices[0]
        return top_indices

    def update(self, reward: float, x: NDArray):
        """
        reward: observed reward of the chosen arm\n
        x: feature vector of the chosen arm, shape (n_features,)
        """
        self.A += np.outer(x, x)
        self.b += reward * x

    def get_theta(self):
        A_inv = np.linalg.inv(self.A)
        theta = A_inv @ self.b
        return theta


linucb_model = SharedLinUCBModel.load(settings.linucb_model_path)
print("LinUCB model loaded")

with open(settings.post_features_path, "rb") as f:
    post_features = pickle.load(f)
    print(f"{settings.post_features_path} loaded")


def build_learner_vector(learner_history: list[tuple[int, float]]) -> NDArray:
    vec = np.zeros(settings.item_feature_dim)
    total_weight = 0.0
    for post_id, reward in learner_history:
        item_vec = post_features[post_id]
        vec += reward * item_vec
        total_weight += abs(reward)

    if total_weight > 0:
        vec /= total_weight

    return vec


def build_arm_vector(item_vector: NDArray, learner_vector: NDArray) -> NDArray:
    item_emb = item_vector[: settings.item_content_emb_dim]
    item_extra = item_vector[settings.item_content_emb_dim :]
    learner_emb = learner_vector[: settings.item_content_emb_dim]
    learner_extra = learner_vector[settings.item_content_emb_dim :]

    sim = cosine_sim(item_emb, learner_emb)
    arm_vector = np.concatenate(
        [
            np.array([sim]),  # shape (1,)
            item_extra,  # shape (3,)
            learner_extra,  # shape (3,)
        ]
    )
    return arm_vector


def rank_posts(
    learner_history: list[tuple[int, float]],
    candidate_post_ids: list[int],
    top_k: int,
):
    learner_vector = build_learner_vector(learner_history)
    arms = [
        (pid, build_arm_vector(post_features[pid], learner_vector))
        for pid in candidate_post_ids
    ]
    arm_features = [arm_vec for _, arm_vec in arms]
    chosen_indices = linucb_model.select_arm(arm_features, top_k)
    results = [arms[i] for i in chosen_indices]

    # chosen_post_ids, chosen_arm_features
    return tuple(zip(*results)) if results else ([], [])


def update_model(reward: float, arm_feature: str):
    arm_vector = np.array(json.loads(arm_feature))
    linucb_model.update(reward, arm_vector)
    print("linUCB model updated")
