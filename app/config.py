import logging
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_PATH = LOG_DIR / "app.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.propagate = False  # prevent propagate to the system logger


file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter("[APP] %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class Settings(BaseSettings):
    """
    When create a Settings() object, its properties will be as the following:
    - Look for environment variables
    - If not set, read them from the .env file
    - If not in .env, fallback to default values
    """

    # Databases
    database_url: str
    redis_url: str
    brick_max_words: int = 25
    brick_avg_word_len: int = 8
    context_max_chars: int = 500
    max_path_len: int = 512

    # Servers and Cloud
    inference_url: str
    asset_base_url: str

    google_app_email_address: str
    google_app_password: str

    # Security
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    otp_expire_minutes: int = 5
    secured_connection: bool = False

    # Media
    brick_audios_folder: str = "brick-audios"
    learner_audios_folder: str = "learner-audios"
    snippets_folder: str = "snippets-audios"

    # Context search
    semantic_emb_dim: int = 384  # all-MiniLM-L6-v2

    # load value from the .env file
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.google_app_email_address,
    MAIL_PASSWORD=settings.google_app_password,
    MAIL_FROM=settings.google_app_email_address,
    MAIL_PORT=465,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)
fast_mail = FastMail(mail_config)
