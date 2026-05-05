"""Configuración 12-Factor App via variables de entorno."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://radar_user:radar_pass@localhost:5432/radar_db"
    log_level: str = "info"
    environment: str = "development"
    image_source_type: str = "local"
    image_source_path: str = "./data/radar_images"
    image_source_url: str = ""


settings = Settings()

