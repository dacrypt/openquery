"""Tests for core.rate_limit — token bucket rate limiter."""

from __future__ import annotations

import threading

from openquery.core.rate_limit import RateLimiter


class TestRateLimiter:
    """Tests for the RateLimiter manager."""

    def test_default_initialization(self):
        limiter = RateLimiter()
        # Should allow requests immediately (bucket starts full)
        assert limiter.is_allowed("test.source") is True

    def test_custom_default_rpm(self):
        limiter = RateLimiter(default_rpm=5)
        # Should work with any source name
        assert limiter.is_allowed("foo") is True

    def test_configure_custom_rpm(self):
        limiter = RateLimiter()
        limiter.configure("co.simit", rpm=30)
        # After configuring, should still allow requests (new bucket starts full)
        assert limiter.is_allowed("co.simit") is True

    def test_acquire_blocks_and_returns(self):
        """acquire() should return (not block forever) when tokens are available."""
        limiter = RateLimiter(default_rpm=60)
        limiter.acquire("test")  # Should not block — bucket starts full

    def test_is_allowed_returns_false_when_exhausted(self):
        """After exhausting tokens, is_allowed returns False."""
        limiter = RateLimiter(default_rpm=2)
        assert limiter.is_allowed("src") is True
        assert limiter.is_allowed("src") is True
        # Bucket should be empty now
        assert limiter.is_allowed("src") is False

    def test_separate_buckets_per_source(self):
        """Different sources have independent buckets."""
        limiter = RateLimiter(default_rpm=1)
        assert limiter.is_allowed("source_a") is True
        assert limiter.is_allowed("source_a") is False
        # source_b should still have tokens
        assert limiter.is_allowed("source_b") is True

    def test_configure_overrides_default(self):
        limiter = RateLimiter(default_rpm=1)
        limiter.configure("fast_source", rpm=100)
        # Fast source should allow many requests
        for _ in range(50):
            assert limiter.is_allowed("fast_source") is True

    def test_thread_safety(self):
        """Concurrent access should not crash."""
        limiter = RateLimiter(default_rpm=1000)
        results = []

        def worker():
            for _ in range(10):
                results.append(limiter.is_allowed("concurrent"))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        # At least some should be True (bucket starts with 1000 tokens)
        assert any(results)

    def test_acquire_with_low_rpm(self):
        """acquire() on a very low RPM bucket should still work for first token."""
        limiter = RateLimiter(default_rpm=1)
        limiter.acquire("slow")  # First call should not block

    def test_min_rpm_is_one(self):
        """RPM of 0 should be clamped to 1."""
        limiter = RateLimiter(default_rpm=0)
        # Should not raise
        assert limiter.is_allowed("zero_rpm") is True
