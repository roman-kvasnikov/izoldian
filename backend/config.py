from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Paths
    data_dir: str = "./data"
    db_path: str = "./data/izoldian.db"

    # Session
    session_max_age_days: int = 7

    # Auth control
    user_signup: bool = True
    disable_internal_auth: bool = False

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
