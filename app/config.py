from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    When you instantiate Settings(), Pydantic will:

    Look for environment variables first (DATABASE_URL, SEED_ON_STARTUP)

    If not set, read them from the .env file

    If not in .env, fallback to default values ("database.db", True)
    """
    database_url: str
    secret_key: str
    seed_on_startup: bool = True
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    class Config:
        env_file = ".env"  # load values from .env file
        env_file_encoding = "utf-8"


settings = Settings()
