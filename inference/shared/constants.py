import os
from pathlib import Path

# If ../logs exists (Local Dev), write to lisenare/logs/
# If it doesn't (Docker Production), write to /app/logs/
LOG_DIR = (
    Path("../logs").resolve()
    if os.path.exists("../logs")
    else Path("logs").resolve()
)
LOG_DIR.mkdir(parents=True, exist_ok=True)

BRICK_MAX_WORDS = 25
BRICK_AVG_WORD_LEN = 8
PASS_SCORE = 0.8
