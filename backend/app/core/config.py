from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    fortyguard_api_key: str
    fortyguard_base_url: str = "https://api.fortyguard.com"

    database_url: str
    redis_url: str

    environment: str = "development"
    poll_interval_seconds: float = 2.0
    poll_timeout_seconds: float = 120.0


settings = Settings()