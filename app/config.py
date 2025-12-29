from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    When you instantiate Settings(), Pydantic will:
    - Look for environment variables first
    - If not set, read them from the .env file
    - If not in .env, fallback to default values
    """
    db_url: str = "lisenare.db"
    secret_key: str
    google_app_email_address: str
    google_app_password: str

    # Audio
    brick_folder: str = "bricks"
    class Config:
        env_file = ".env"  # load values from .env file
        env_file_encoding = "utf-8"

settings = Settings()
