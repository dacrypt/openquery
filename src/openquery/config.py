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

    # Captcha — image-based
    captcha_solver: str = "ocr"  # ocr, 2captcha, chained
    two_captcha_api_key: str = ""

    # Captcha — reCAPTCHA v2 providers (set API key to enable)
    capsolver_api_key: str = ""
    capmonster_api_key: str = ""
    anticaptcha_api_key: str = ""

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_default_rpm: int = 10

    # Browser
    browser_headless: bool = True
    browser_timeout: float = 60.0

    # Proxy — residential/rotating proxy for WAF bypass
    proxy_url: str = ""  # e.g. http://user:pass@proxy.example.com:8080
    proxy_country: str = ""  # ISO country code for geo-targeting (if proxy supports)

    # Circuit breaker
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown: float = 60.0

    # External API keys
    wto_api_key: str = ""  # WTO Timeseries API (register at apiportal.wto.org)
    sam_api_key: str = ""  # SAM.gov API (register at api.sam.gov)
    br_transparencia_api_key: str = ""  # Brazil Portal Transparencia

    # Logging
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
