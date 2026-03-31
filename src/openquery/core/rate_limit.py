"""Token-bucket rate limiter, keyed by source name."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Per-source token-bucket rate limiter.

    Each source gets its own bucket with configurable requests-per-minute.
    Thread-safe.
    """

    def __init__(self, default_rpm: int = 10) -> None:
        self._default_rpm = default_rpm
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def configure(self, source: str, rpm: int) -> None:
        """Set a custom rate limit for a specific source."""
        with self._lock:
            self._buckets[source] = _Bucket(rpm)

    def acquire(self, source: str) -> None:
        """Block until a token is available for the given source."""
        bucket = self._get_bucket(source)
        bucket.acquire()

    def is_allowed(self, source: str) -> bool:
        """Non-blocking check if a request is allowed."""
        bucket = self._get_bucket(source)
        return bucket.try_acquire()

    def _get_bucket(self, source: str) -> _Bucket:
        with self._lock:
            if source not in self._buckets:
                self._buckets[source] = _Bucket(self._default_rpm)
            return self._buckets[source]


class _Bucket:
    """Single token bucket."""

    def __init__(self, rpm: int) -> None:
        self._rpm = max(rpm, 1)
        self._interval = 60.0 / self._rpm  # seconds between tokens
        self._tokens = float(self._rpm)
        self._max_tokens = float(self._rpm)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed / self._interval
        self._tokens = min(self._max_tokens, self._tokens + new_tokens)
        self._last_refill = now

    def acquire(self) -> None:
        """Block until a token is available."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait_time = (1.0 - self._tokens) * self._interval
            time.sleep(wait_time)

    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking."""
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False
