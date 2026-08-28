from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    fortyguard_api_key: str
    fortyguard_base_url: str = "https://api.fortyguard.com"

    database_url: str
    redis_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    environment: str = "development"
    poll_interval_seconds: float = 2.0
    poll_timeout_seconds: float = 120.0

    cors_allowed_origins: str = "http://localhost:5173"


settings = Settings()