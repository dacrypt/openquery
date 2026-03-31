"""Configuration management using pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OpenQuery configuration.

    All settings can be overridden via environment variables prefixed with OPENQUERY_.
    Example: OPENQUERY_API_KEY=secret, OPENQUERY_BROWSER_HEADLESS=false
    """

    model_config = SettingsConfigDict(
        env_prefix="OPENQUERY_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str = ""

    # Cache
    cache_backend: str = "memory"  # memory, redis, sqlite
    cache_ttl_default: int = 3600  # 1 hour
    redis_url: str = "redis://localhost:6379/0"
    sqlite_path: str = "~/.openquery/cache.db"

    # Captcha
    captcha_solver: str = "ocr"  # ocr, 2captcha, chained
    two_captcha_api_key: str = ""

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_default_rpm: int = 10

    # Browser
    browser_headless: bool = True
    browser_timeout: float = 30.0

    # Logging
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
