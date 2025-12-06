# plot_and_report_rewards.py
import sys
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

DATA_PATH = Path("eval_rewards.npz")

def pct_improve(base, target):
    """Tính % cải thiện từ base -> target"""
    return (target - base) / (abs(base) + 1e-8) * 100

def safe_stats(arr):
    return float(np.mean(arr)), float(np.std(arr)), int(len(arr))

def main():
    if not DATA_PATH.exists():
        print(f"❌ Không tìm thấy file: {DATA_PATH}. Hãy chắc bạn đã chạy script lưu rewards trước.")
        sys.exit(1)

    data = np.load(DATA_PATH)

    # Load đúng key
    try:
        ppo_stoch = data["ppo_stoch"]
        ppo_det = data["ppo_det"]
        random_rewards = data["random"]
        cosine_rewards = data["cosine"]
    except KeyError as e:
        print("❌ File .npz không chứa khóa mong đợi:", e)
        print("   Các khóa trong file:", list(data.keys()))
        sys.exit(1)

    # === Statistics ===
    mean_ppo, std_ppo, n_ppo = safe_stats(ppo_stoch)
    mean_det, std_det, n_det = safe_stats(ppo_det)
    mean_rand, std_rand, n_rand = safe_stats(random_rewards)
    mean_cos, std_cos, n_cos = safe_stats(cosine_rewards)

    print("\n=== Summary statistics (mean ± std, n) ===")
    print(f"PPO (stochastic)   : {mean_ppo:.4f} ± {std_ppo:.4f} (n={n_ppo})")
    print(f"PPO (deterministic): {mean_det:.4f} ± {std_det:.4f} (n={n_det})")
    print(f"Random baseline    : {mean_rand:.4f} ± {std_rand:.4f} (n={n_rand})")
    print(f"Cosine baseline    : {mean_cos:.4f} ± {std_cos:.4f} (n={n_cos})")

    # === Improvements ===
    print("\n=== Improvement (%) ===")
    print(f"PPO (stoch) vs Random   : {pct_improve(mean_rand, mean_ppo):.2f}%")
    print(f"PPO (stoch) vs Cosine   : {pct_improve(mean_cos, mean_ppo):.2f}%")
    print(f"PPO (det) vs Random     : {pct_improve(mean_rand, mean_det):.2f}%")
    print(f"PPO (det) vs Cosine     : {pct_improve(mean_cos, mean_det):.2f}%")

    # === Violin Plot ===
    sns.set(style="whitegrid")
    plt.figure(figsize=(10, 6))

    data_list = [
        random_rewards,
        cosine_rewards,
        ppo_stoch,
        ppo_det,
    ]

    sns.violinplot(data=data_list, inner="quartile")
    plt.xticks([0, 1, 2, 3], ["Random", "Cosine", "PPO Stoch", "PPO Det"])
    plt.ylabel("Total Episode Reward")
    plt.title("Violin Plot: Reward Distributions")

    out_png = "reward_violins.png"
    plt.savefig(out_png)
    print(f"\n✔ Violin plot saved to: {out_png}")

if __name__ == "__main__":
    main()
