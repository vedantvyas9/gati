"""Application configuration using Pydantic settings."""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings."""

    # Application settings
    app_name: str = "GATI Backend"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True

    # Database settings
    database_url: str = "sqlite+aiosqlite:///./gati.db"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600

    # CORS settings
    cors_origins: str = "*"
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # API settings
    api_prefix: str = "/api"
    health_check_path: str = "/health"

    # Event processing settings
    max_batch_size: int = 10000
    max_event_size_mb: float = 100.0

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_cors_origins(self) -> list[str]:
        """Parse CORS origins from string to list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
