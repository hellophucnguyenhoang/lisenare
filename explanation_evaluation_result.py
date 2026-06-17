import pandas as pd

CSV_PATH = "evaluation_results.csv"

df = pd.read_csv(CSV_PATH)

# chỉ giữ các request thành công
if "success" in df.columns:
    df = df[df["success"]].copy()

print("=" * 60)
print("OVERALL STATISTICS")
print("=" * 60)

total_samples = len(df)

avg_before = df["familiarity_before"].mean()
avg_after = df["familiarity_after"].mean()

avg_improvement = df["familiarity_improvement"].mean()

median_improvement = df["familiarity_improvement"].median()

max_improvement = df["familiarity_improvement"].max()
min_improvement = df["familiarity_improvement"].min()

improved_count = (df["familiarity_improvement"] > 0).sum()

improved_ratio = improved_count / total_samples * 100

avg_time = df["response_time_ms"].mean()

median_time = df["response_time_ms"].median()

print(f"Samples: {total_samples}")

print()
print("Familiarity")
print(f"Before       : {avg_before:.4f}")
print(f"After        : {avg_after:.4f}")
print(f"Improvement  : {avg_improvement:.4f}")

if avg_before > 0:
    relative_gain = (avg_improvement / avg_before) * 100

    print(f"Relative gain: {relative_gain:.2f}%")

print()
print(f"Median improvement : {median_improvement:.4f}")
print(f"Max improvement    : {max_improvement:.4f}")
print(f"Min improvement    : {min_improvement:.4f}")

print()
print(f"Improved samples   : {improved_count}/{total_samples}")
print(f"Improved ratio     : {improved_ratio:.2f}%")

print()
print("Response Time")
print(f"Average : {avg_time:.2f} ms")
print(f"Median  : {median_time:.2f} ms")

print()
print("=" * 60)
print("CEFR BREAKDOWN")
print("=" * 60)

for level in ["A1", "A2", "B1", "B2", "C1"]:
    level_df = df[df["level"] == level]

    if len(level_df) == 0:
        continue

    before = level_df["familiarity_before"].mean()
    after = level_df["familiarity_after"].mean()

    improvement = level_df["familiarity_improvement"].mean()

    improved_ratio = (level_df["familiarity_improvement"] > 0).mean() * 100

    response_time = level_df["response_time_ms"].mean()

    print()
    print(f"[{level}]")
    print(f"Samples           : {len(level_df)}")
    print(f"Before familiarity: {before:.4f}")
    print(f"After familiarity : {after:.4f}")
    print(f"Improvement       : {improvement:.4f}")
    print(f"Improved ratio    : {improved_ratio:.2f}%")
    print(f"Avg response time : {response_time:.2f} ms")

print()
print("=" * 60)
print("TOP 10 MOST IMPROVED WORDS")
print("=" * 60)

top10 = df.sort_values(
    by="familiarity_improvement",
    ascending=False,
).head(10)

for _, row in top10.iterrows():
    print(f"{row['target_term']:20}{row['familiarity_improvement']:.4f}")

print()
print("=" * 60)
print("TOP 10 LEAST IMPROVED WORDS")
print("=" * 60)

bottom10 = df.sort_values(
    by="familiarity_improvement",
    ascending=True,
).head(10)

for _, row in bottom10.iterrows():
    print(f"{row['target_term']:20}{row['familiarity_improvement']:.4f}")
