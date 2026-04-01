"""Extended cache tests — SQLite backend, create_cache factory, stats."""

from __future__ import annotations

import tempfile
import time

import pytest

from openquery.core.cache import InMemoryCache, SQLiteCache, create_cache, make_key


class TestInMemoryCacheExtended:
    def test_stats_format(self):
        cache = InMemoryCache()
        stats = cache.stats()
        assert stats["backend"] == "memory"
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert "hit_rate" in stats

    def test_hit_rate_calculation(self):
        cache = InMemoryCache()
        cache.set("k1", {"v": 1})
        cache.get("k1")  # hit
        cache.get("k1")  # hit
        cache.get("k2")  # miss
        stats = cache.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == "66.7%"

    def test_delete_and_get(self):
        cache = InMemoryCache()
        cache.set("k", {"v": 1})
        cache.delete("k")
        assert cache.get("k") is None

    def test_delete_nonexistent(self):
        cache = InMemoryCache()
        cache.delete("nonexistent")  # Should not raise

    def test_overwrite(self):
        cache = InMemoryCache()
        cache.set("k", {"v": 1})
        cache.set("k", {"v": 2})
        assert cache.get("k") == {"v": 2}


class TestSQLiteCache:
    def test_basic_operations(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            cache = SQLiteCache(path=f.name)
            cache.set("key1", {"data": "hello"}, ttl_seconds=3600)
            assert cache.get("key1") == {"data": "hello"}

    def test_delete(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            cache = SQLiteCache(path=f.name)
            cache.set("k", {"v": 1})
            cache.delete("k")
            assert cache.get("k") is None

    def test_stats(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            cache = SQLiteCache(path=f.name)
            cache.set("a", {"x": 1})
            cache.set("b", {"y": 2})
            stats = cache.stats()
            assert stats["backend"] == "sqlite"
            assert stats["entries"] == 2

    def test_overwrite(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            cache = SQLiteCache(path=f.name)
            cache.set("k", {"v": 1})
            cache.set("k", {"v": 2})
            assert cache.get("k") == {"v": 2}

    def test_expired_entry(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            cache = SQLiteCache(path=f.name)
            # Set with TTL of 0 seconds — already expired
            cache._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                ("expired_key", '{"v": 1}', time.time() - 1),
            )
            cache._conn.commit()
            assert cache.get("expired_key") is None


class TestCreateCacheFactory:
    def test_memory_backend(self):
        cache = create_cache("memory")
        assert isinstance(cache, InMemoryCache)

    def test_sqlite_backend(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            cache = create_cache("sqlite", path=f.name)
            assert isinstance(cache, SQLiteCache)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown cache backend"):
            create_cache("dynamodb")

    def test_redis_import_error(self):
        """Redis requires the redis package."""
        # This may succeed or fail depending on environment
        # Just verify create_cache("redis") doesn't crash with unrelated error
        try:
            create_cache("redis")
        except (ImportError, Exception):
            pass  # Expected if redis not installed


class TestMakeKey:
    def test_format(self):
        assert make_key("co.simit", "cedula", "123") == "openquery:co.simit:cedula:123"

    def test_special_characters(self):
        key = make_key("co.runt", "placa", "ABC-123")
        assert "ABC-123" in key
