from pathlib import Path

CONTEXT_MAX_CHARS = 500
MAX_PATH_LEN = 512
OTP_EXPIRE_MINUTES = 5
SEMANTIC_EMB_DIM = 384  # all-MiniLM-L6-v2

ASSETS_DIR = Path("lisenare-assets")
LEARNER_AUDIOS_DIR = Path("learner-audios")
GENERATED_AUDIOS_DIR = Path("generated-audios")

AUDIO_CACHE_TTL_SECONDS = 86400  # 24 hours in seconds
BRICK_CACHE_PREFIX = "brick_audio:"
AUDIO_CATCH_PREFIX = "cached_audio:"
