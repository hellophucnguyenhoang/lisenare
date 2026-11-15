import os

from shared.logger import setup_logger

logger = setup_logger(
    "inference",
    "INFERENCE",
    os.getenv("TARGET_ENV", ".env") == ".env",
)
