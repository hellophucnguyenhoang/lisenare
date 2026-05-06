from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    When create a Settings() object, its properties will be as the following:
    - Look for environment variables
    - If not set, read them from the .env file
    - If not in .env, fallback to default values
    """

    # Databases
    database_url: str

    # Servers
    ai_model_server_url: str
    gcs_base_url: str

    # Security
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int = 10
    otp_expire_minutes: int = 5
    google_app_email_address: str
    google_app_password: str
    gemini_api_key: str

    # Media
    brick_audios_folder: str = "brick-audios"
    learner_audios_folder: str = "learner-audios"
    snippets_folder: str = "snippets-data"

    # Context search
    semantic_emb_dim: int = 384  # all-MiniLM-L6-v2

    # Recommendation: LinUCB
    post_features_path: str = "models/post_features.pkl"
    linucb_model_path: str = "models/linucb_weights.npz"
    item_feature_dim: int = 387
    item_content_emb_dim: int = 384
    extra_feature_dim: int = 3

    # load value from the .env file
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
