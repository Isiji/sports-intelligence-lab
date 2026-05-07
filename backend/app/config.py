from pydantic_settings import BaseSettings, SettingsConfigDict


def normalized_database_url(url: str) -> str:
    """
    Normalize PostgreSQL URLs so SQLAlchemy uses psycopg v3.

    Allows:
    postgresql://...
    postgresql+psycopg://...
    sqlite:///...
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


class Settings(BaseSettings):
    app_name: str = "Sports Intelligence Lab"
    env: str = "development"

    database_url: str = "sqlite:///sportslab.db"

    random_seed: int = 42

    sports_api_provider: str = "api-football"
    sports_api_key: str | None = None
    sports_api_base_url: str = "https://v3.football.api-sports.io"

    sports_api_daily_limit: int = 7000
    sports_api_safety_buffer: int = 800
    sports_api_retry_attempts: int = 3
    sports_api_retry_sleep_seconds: int = 10
    sports_api_timeout_seconds: int = 30

    model_config = SettingsConfigDict(
        env_prefix="SPORTSLAB_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()