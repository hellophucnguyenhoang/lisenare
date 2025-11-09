# reading_level_classifier.py
import re
from collections import Counter
from pathlib import Path

# ------------------------------
# Load vocab lists (once only)
# ------------------------------

LEVEL_NAMES = ["A1", "A2", "B1", "B2", "C1"]
VOCAB_DIR = Path(__file__).parent / "processed_vocab"
print("Loading vocab lists from", VOCAB_DIR)

vocab_levels = []
for level in LEVEL_NAMES:
    path = VOCAB_DIR / f"{level}.txt"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run process_vocab_lists.py first.")
    with open(path, "r", encoding="utf-8") as f:
        vocab_levels.append(set(line.strip() for line in f if line.strip()))

# ------------------------------
# Main function
# ------------------------------

def naive_classify_reading(text: str) -> int:
    """
    Classify a given text into CEFR levels:
    0=A1, 1=A2, 2=B1, 3=B2, 4=C1, 5=C2 (default if unknown).
    """
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return 5  # empty text

    level_counts = Counter()

    for w in words:
        found = False
        for i, vocab in enumerate(vocab_levels):
            if w in vocab:
                level_counts[i] += 1
                found = True
                break
        if not found:
            level_counts[5] += 1  # treat as C2

    total = sum(level_counts.values())
    avg_level = sum(lvl * cnt for lvl, cnt in level_counts.items()) / total
    return round(avg_level)

def classify_reading(text, power: float = 2.0):
    """
    Exponential weighting, higher levels count more.
    """
    words = re.findall(r"[a-zA-Z]+", text.lower())
    level_counts = Counter()

    for w in words:
        for i, vocab in enumerate(vocab_levels):
            if w in vocab:
                level_counts[i] += 1
                break
        else:
            level_counts[5] += 1  # unknown = C2

    if not level_counts:
        return 5

    total = sum(level_counts.values())
    weighted_sum = sum((i ** power) * c for i, c in level_counts.items())
    score = weighted_sum / total
    return round(score ** (1 / power))  # normalize back to 0–5 scale


# ------------------------------
# Example
# ------------------------------
if __name__ == "__main__":
    easy_text = "I have a cat and a dog. They play together every day."
    hard_text = "Quantum mechanics describes the peculiar behaviors of particles."

    print("Easy text level:", classify_reading(easy_text))  # 0–1
    print("Hard text level:", classify_reading(hard_text))  # 4–5
