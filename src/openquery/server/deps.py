"""FastAPI dependency injection."""

from __future__ import annotations

from functools import lru_cache

from openquery.config import get_settings
from openquery.core.cache import CacheBackend, create_cache
from openquery.core.rate_limit import RateLimiter


@lru_cache
def get_cache() -> CacheBackend:
    """Get the shared cache backend."""
    settings = get_settings()
    kwargs = {}
    if settings.cache_backend == "redis":
        kwargs["url"] = settings.redis_url
    elif settings.cache_backend == "sqlite":
        kwargs["path"] = settings.sqlite_path
    return create_cache(settings.cache_backend, **kwargs)


@lru_cache
def get_rate_limiter() -> RateLimiter:
    """Get the shared rate limiter."""
    settings = get_settings()
    return RateLimiter(default_rpm=settings.rate_limit_default_rpm)
