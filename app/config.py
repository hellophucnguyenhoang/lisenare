from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    When you instantiate Settings(), Pydantic will:

    Look for environment variables first (DATABASE_URL, SEED_ON_STARTUP)

    If not set, read them from the .env file

    If not in .env, fallback to default values ("database.db", True)
    """
    database_url: str = "./database.db"
    ytb_subtitles_db_url: str = "./youtube_subtitles_copy.db"
    secret_key: str
    google_app_email_address: str
    google_app_password: str
    otp_expire_minutes: int = 5
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    item_embedding_dim: int = 10
    recent_history_size: int = 5
    recommend_batch_size: int = 3

    class Config:
        env_file = ".env"  # load values from .env file
        env_file_encoding = "utf-8"


settings = Settings()
