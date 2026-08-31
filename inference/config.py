import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_PATH = LOG_DIR / "inference.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("inference")
logger.setLevel(logging.INFO)
logger.propagate = False  # prevent propagate to the system logger


file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter(
    "[INFERENCE] %(levelname)s - %(message)s"
)
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
