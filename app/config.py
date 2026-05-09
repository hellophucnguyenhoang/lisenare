from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    When create a Settings() object, Pydantic will:
    - Look for environment variables first
    - If not set, read them from the .env file
    - If not in .env, fallback to default values
    """

    db_path: str = "lisenare.db"
    ytb_subtitle_db_path: str = "ytb_subtitles.db"
    chroma_context_path: str = "chroma_context"
    ai_model_server_url: str

    # Security
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int = 1 * 24
    otp_expire_minutes: int = 5
    google_app_email_address: str
    google_app_password: str

    # Media
    broken_report_file: str = "broken_bricks.txt"
    brick_audios_folder: str = "brick-audios"
    learner_audios_folder: str = "learner-audios"
    snippets_folder: str = "snippets-data"

    # Recommendation: LinUCB
    post_features_path: str = "models/post_features.pkl"
    linucb_model_path: str = "models/linucb_weights.npz"
    item_feature_dim: int = 387
    item_content_emb_dim: int = 384
    extra_feature_dim: int = 3

    # load value from the .env file
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
