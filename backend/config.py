import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    secret_key: str = "change-me-in-production"

    # Paths
    data_dir: str = os.environ.get("DATA_DIR", "./data")
    db_path: str = os.environ.get("DB_PATH", "./data/izoldian.db")

    # Session
    session_max_age_days: int = 7

    # OIDC (Authelia)
    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""
    oidc_scopes: str = "openid profile email"

    # CORS
    cors_origins: str = "*"

    class Config:
        env_prefix = ""
        env_file = ".env"


settings = Settings()
