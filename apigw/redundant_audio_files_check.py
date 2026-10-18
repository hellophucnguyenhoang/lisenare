import shutil
from pathlib import Path

import pandas as pd

from config import logger

# Paths
CSV_PATH = Path("bricks-metadata.csv")
AUDIO_DIR = Path("lisenare-assets/system-brick-audios")
REDUNDANT_DIR = Path("lisenare-assets/system-brick-audios-redundant")

# Read CSV
df = pd.read_csv(CSV_PATH)

# Get audio filenames from CSV
csv_audio_files = set(df["source_audio_file"].dropna().astype(str).str.strip())

# Get actual audio files in the folder
folder_audio_files = {
    file.name for file in AUDIO_DIR.iterdir() if file.is_file()
}

# Files expected by CSV but missing from folder
missing_files = csv_audio_files - folder_audio_files

# Files in folder but not referenced by CSV
redundant_files = folder_audio_files - csv_audio_files

# Log summary
logger.info(f"Audio files in CSV:       {len(csv_audio_files)}")
logger.info(f"Audio files in folder:    {len(folder_audio_files)}")
logger.info(f"Missing audio files:      {len(missing_files)}")
logger.info(f"Redundant audio files:    {len(redundant_files)}")

# Log missing files
if missing_files:
    logger.warning("Missing audio files:")
    for filename in sorted(missing_files):
        logger.warning(f"  {filename}")
else:
    logger.info("No missing audio files.")

# Move redundant files
if redundant_files:
    REDUNDANT_DIR.mkdir(parents=True, exist_ok=True)

    for filename in sorted(redundant_files):
        source = AUDIO_DIR / filename
        destination = REDUNDANT_DIR / filename

        shutil.move(str(source), str(destination))

    logger.info(
        f"Moved {len(redundant_files)} redundant files to: {REDUNDANT_DIR}"
    )
else:
    logger.info("No redundant audio files.")
