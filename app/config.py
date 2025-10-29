from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    When you instantiate Settings(), Pydantic will:

    Look for environment variables first (DATABASE_FILE, SEED_ON_STARTUP)

    If not set, read them from the .env file

    If not in .env, fallback to default values ("database.db", True)
    """
    database_file: str = "database.db"
    seed_on_startup: bool = True

    class Config:
        env_file = ".env"  # load values from .env file
        env_file_encoding = "utf-8"


settings = Settings()
