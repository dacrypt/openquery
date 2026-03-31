"""Unit tests for cache backends."""

from __future__ import annotations

from openquery.core.cache import InMemoryCache, make_key


class TestMakeKey:
    def test_format(self):
        key = make_key("co.simit", "cedula", "12345678")
        assert key == "openquery:co.simit:cedula:12345678"


class TestInMemoryCache:
    def test_set_and_get(self):
        cache = InMemoryCache()
        cache.set("test", {"foo": "bar"})
        assert cache.get("test") == {"foo": "bar"}

    def test_get_missing(self):
        cache = InMemoryCache()
        assert cache.get("nonexistent") is None

    def test_delete(self):
        cache = InMemoryCache()
        cache.set("key", {"data": 1})
        cache.delete("key")
        assert cache.get("key") is None

    def test_stats(self):
        cache = InMemoryCache(maxsize=100)
        cache.set("a", {"x": 1})
        cache.get("a")  # hit
        cache.get("b")  # miss

        stats = cache.stats()
        assert stats["backend"] == "memory"
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
