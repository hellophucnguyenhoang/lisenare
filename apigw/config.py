import logging
import os
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail
from pydantic_settings import BaseSettings, SettingsConfigDict

# If ../logs exists (Local Dev), go up to lisenare/logs/
# If it doesn't (Docker Production), write to /app/logs/
if os.path.exists("../logs"):
    LOG_DIR = Path("../logs").resolve()
else:
    LOG_DIR = Path("logs").resolve()

LOG_FILE_PATH = LOG_DIR / "apigw.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("apigw")
logger.setLevel(logging.INFO)
logger.propagate = False  # prevent propagate to the system logger


file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter("[APIGW] %(levelname)s - %(message)s")
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
    db_user: str
    db_password: str
    db_name: str

    # Servers and Cloud
    inference_url: str
    asset_base_url: str

    google_app_email_address: str
    google_app_password: str

    # Security
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    secured_connection: bool = False

    # Media
    system_brick_audios_folder: str = "lisenare-assets/system-brick-audios"
    learner_audios_folder: str = "lisenare-assets/learner-audios"
    generated_audios_folder: str = "lisenare-assets/generated-audios"

    # load value from the .env file
    model_config = SettingsConfigDict(env_file=".env")

    @property
    def database_url(self) -> str:
        # Connects directly via Docker internal network gateway using the name 'database'
        return f"postgresql://{self.db_user}:{self.db_password}@database:5432/{self.db_name}"


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
