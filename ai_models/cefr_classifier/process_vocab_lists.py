# process_vocab_lists.py
import re
from pathlib import Path

RAW_FILES = {
    "A1": "a1.txt",
    "A2": "a2.txt",
    "B1": "b1.txt",
    "B2": "b2.txt",
    "C1": "c1.txt"
}

OUTPUT_DIR = Path("processed_vocab")
OUTPUT_DIR.mkdir(exist_ok=True)


def extract_clean_words(input_path: str):
    words = set()
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Take first word only
            word = line.split()[0].lower()
            # Remove digits
            word = re.sub(r"\d+", "", word)
            # Only alphabetic words
            if re.match(r"^[a-zA-Z]+$", word):
                words.add(word)
    return sorted(words)


def process_all():
    for level, filename in RAW_FILES.items():
        words = extract_clean_words(filename)
        output_path = OUTPUT_DIR / f"{level}.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(words))
        print(f"✅ Saved {len(words)} words to {output_path}")


if __name__ == "__main__":
    process_all()
