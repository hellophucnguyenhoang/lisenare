from pathlib import Path

import pandas as pd
from mutagen import File as MutagenFile
from tqdm import tqdm  # Great for seeing progress


def add_durations_to_csv(csv_input: str, csv_output: str, audio_folder: str):
    df = pd.read_csv(csv_input)
    audio_dir = Path(audio_folder)
    durations = []

    print("Calculating durations...")
    for filename in tqdm(df["filename"]):
        path = audio_dir / filename
        try:
            audio_info = MutagenFile(path).info
            durations.append(audio_info.length)
        except Exception:
            print("no audio found")
            durations.append(0.0)  # Handle missing files

    df["duration"] = durations
    df.to_csv(csv_output, index=False)
    print(f"Saved updated CSV to {csv_output}")


# Usage
add_durations_to_csv(
    "cv-valid-test.csv", "snippets-metadata.csv", "./snippets-data"
)
