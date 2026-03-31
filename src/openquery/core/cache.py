"""Cache backends for storing query results.

Supports in-memory (default), Redis, and SQLite backends.
Cache keys follow the pattern: openquery:{source}:{doc_type}:{doc_number}
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


def make_key(source: str, doc_type: str, doc_number: str) -> str:
    """Build a cache key."""
    return f"openquery:{source}:{doc_type}:{doc_number}"


class CacheBackend(ABC):
    """Abstract cache backend."""

    @abstractmethod
    def get(self, key: str) -> dict | None:
        """Get a cached value. Returns None if not found or expired."""

    @abstractmethod
    def set(self, key: str, value: dict, ttl_seconds: int = 3600) -> None:
        """Store a value with TTL."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a cached value."""

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        return {}


class InMemoryCache(CacheBackend):
    """In-memory TTL cache using cachetools."""

    def __init__(self, maxsize: int = 1000, default_ttl: int = 3600) -> None:
        from cachetools import TTLCache

        self._cache = TTLCache(maxsize=maxsize, ttl=default_ttl)
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> dict | None:
        value = self._cache.get(key)
        if value is not None:
            self._hits += 1
            return value
        self._misses += 1
        return None

    def set(self, key: str, value: dict, ttl_seconds: int = 3600) -> None:
        self._cache[key] = value

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def stats(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "size": len(self._cache),
            "maxsize": self._cache.maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / max(self._hits + self._misses, 1):.1%}",
        }


class RedisCache(CacheBackend):
    """Redis-backed cache."""

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        try:
            import redis
        except ImportError as e:
            raise ImportError("redis is required. Install: pip install 'openquery[redis]'") from e
        self._client = redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> dict | None:
        data = self._client.get(key)
        if data:
            return json.loads(data)
        return None

    def set(self, key: str, value: dict, ttl_seconds: int = 3600) -> None:
        self._client.setex(key, ttl_seconds, json.dumps(value, default=str))

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def stats(self) -> dict[str, Any]:
        info = self._client.info("keyspace")
        return {"backend": "redis", "info": info}


class SQLiteCache(CacheBackend):
    """SQLite-backed persistent cache."""

    def __init__(self, path: str = "~/.openquery/cache.db") -> None:
        import os
        import sqlite3

        expanded = os.path.expanduser(path)
        os.makedirs(os.path.dirname(expanded), exist_ok=True)
        self._conn = sqlite3.connect(expanded)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(key TEXT PRIMARY KEY, value TEXT, expires_at REAL)"
        )
        self._conn.commit()

    def get(self, key: str) -> dict | None:
        row = self._conn.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row and row[1] > time.time():
            return json.loads(row[0])
        if row:
            self.delete(key)
        return None

    def set(self, key: str, value: dict, ttl_seconds: int = 3600) -> None:
        expires_at = time.time() + ttl_seconds
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value, default=str), expires_at),
        )
        self._conn.commit()

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        self._conn.commit()

    def stats(self) -> dict[str, Any]:
        count = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        return {"backend": "sqlite", "entries": count}


def create_cache(backend: str = "memory", **kwargs) -> CacheBackend:
    """Factory to create a cache backend by name."""
    if backend == "memory":
        return InMemoryCache(**kwargs)
    elif backend == "redis":
        return RedisCache(**kwargs)
    elif backend == "sqlite":
        return SQLiteCache(**kwargs)
    else:
        raise ValueError(f"Unknown cache backend: {backend}")
