import logging
import os
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    When create a Settings() object, its properties will be as the following:
    - Look for environment variables
    - If not set, read them from the .env file
    - If not in .env, fallback to default values
    """

    # Security
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    secured_connection: bool
    google_app_email_address: str
    google_app_password: str

    # Databases and servers
    db_user: str
    db_password: str
    db_name: str
    db_url: str
    redis_url: str
    inference_url: str
    ollama_host: str

    # Audio cloud storage
    asset_base_url: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_endpoint_url: str
    aws_region_name: str
    bucket_name: str

    # load value from the .env file
    model_config = SettingsConfigDict(env_file=os.getenv("TARGET_ENV", ".env"))

    @property
    def is_production(self) -> bool:
        env_file = self.model_config.get("env_file", "")
        return env_file == ".env"


settings = Settings()


# If ../logs exists (Local Dev), write to lisenare/logs/
# If it doesn't (Docker Production), write to /app/logs/
LOG_DIR = (
    Path("../logs").resolve()
    if os.path.exists("../logs")
    else Path("logs").resolve()
)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger(name: str, prefix: str) -> logging.Logger:
    log_suffix = "" if settings.is_production else ".dev"
    log_file_path = LOG_DIR / f"{name}{log_suffix}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # prevent propagate to the system logger
    # application logs only
    logger.propagate = False

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(f"[{prefix}] %(levelname)s - %(message)s")
    )

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger("apigw", "APIGW")

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
