import os

from fastapi_mail import ConnectionConfig, FastMail
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.logger import setup_logger


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


logger = setup_logger("apigw", "APIGW", settings.is_production)

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
