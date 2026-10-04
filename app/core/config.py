from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Currency Dashboard API"
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/currency"
    frankfurter_base_url: str = "https://api.frankfurter.dev"
    http_timeout_seconds: float = 10.0


settings = Settings()