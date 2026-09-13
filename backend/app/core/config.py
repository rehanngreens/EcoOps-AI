from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
PROJECT_ROOT = Path(__file__).resolve().parents[3]



class Settings(BaseSettings):
    app_name: str = "EcoOps AI"
    app_version: str = "0.1.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    max_upload_size_bytes: int = 1_048_576
    allowed_upload_extensions: str = ".yaml,.yml"

    database_url: str = "postgresql+psycopg://ecoops:ecoops@localhost:5432/ecoops"
    model_dir: Path = PROJECT_ROOT / "ml" / "models"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_upload_extension_list(self) -> list[str]:
        return [
            ext.strip()
            for ext in self.allowed_upload_extensions.split(",")
            if ext.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
