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

    # Fuente de imágenes
    image_source_type: str = "local"
    image_source_path: str = "./data/radar_images"
    radar_gif_source_path: str = ""
    radar_gif_pattern: str = "*.png"
    image_source_url: str = ""

    # Storage de GeoTIFFs generados.
    # En producción / data bank: cambiar esta variable en .env
    geotiff_storage_path: str = "./data/geotiffs"


settings = Settings()