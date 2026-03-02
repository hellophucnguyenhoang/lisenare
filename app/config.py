from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    When create a Settings() object, Pydantic will:
    - Look for environment variables first
    - If not set, read them from the .env file
    - If not in .env, fallback to default values
    """

    db_url: str = "lisenare.db"
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int = 60 * 24
    otp_expire_minutes: int = 5
    google_app_email_address: str
    google_app_password: str
    ai_model_server_url: str
    broken_report_file: str = "broken_audio.txt"
    brick_folder: str = "bricks"

    # load value from the .env file
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
