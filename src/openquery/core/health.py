"""Source health monitoring with inline circuit breaker."""

from __future__ import annotations

import threading
import time
from datetime import datetime

from openquery.models.health import CircuitState, HealthReport, SourceHealth


class _SourceStats:
    """Internal tracking for a single source."""

    __slots__ = (
        "success_count",
        "failure_count",
        "consecutive_failures",
        "total_latency_ms",
        "state",
        "last_check",
        "last_error",
        "opened_at",
    )

    def __init__(self) -> None:
        self.success_count: int = 0
        self.failure_count: int = 0
        self.consecutive_failures: int = 0
        self.total_latency_ms: float = 0.0
        self.state: CircuitState = CircuitState.CLOSED
        self.last_check: float | None = None
        self.last_error: str | None = None
        self.opened_at: float | None = None


class SourceHealthMonitor:
    """Per-source circuit breaker and health tracker.

    State machine:
        CLOSED -> OPEN     (after `threshold` consecutive failures)
        OPEN   -> HALF_OPEN (after `cooldown` seconds)
        HALF_OPEN -> CLOSED (on success)
        HALF_OPEN -> OPEN   (on failure)
    """

    def __init__(self, threshold: int = 5, cooldown: float = 60.0) -> None:
        self._threshold = threshold
        self._cooldown = cooldown
        self._stats: dict[str, _SourceStats] = {}
        self._lock = threading.Lock()

    def _get_stats(self, source: str) -> _SourceStats:
        if source not in self._stats:
            self._stats[source] = _SourceStats()
        return self._stats[source]

    def is_available(self, source: str) -> bool:
        """Check if a source is available (circuit not open)."""
        with self._lock:
            stats = self._get_stats(source)
            if stats.state == CircuitState.CLOSED:
                return True
            if stats.state == CircuitState.OPEN:
                # Check if cooldown has elapsed
                if stats.opened_at and (time.monotonic() - stats.opened_at) >= self._cooldown:
                    stats.state = CircuitState.HALF_OPEN
                    return True
                return False
            # HALF_OPEN — allow one request
            return True

    def record_success(self, source: str, latency_ms: float) -> None:
        """Record a successful query."""
        with self._lock:
            stats = self._get_stats(source)
            stats.success_count += 1
            stats.consecutive_failures = 0
            stats.total_latency_ms += latency_ms
            stats.last_check = time.monotonic()
            if stats.state == CircuitState.HALF_OPEN:
                stats.state = CircuitState.CLOSED

    def record_failure(self, source: str, error: str) -> None:
        """Record a failed query."""
        with self._lock:
            stats = self._get_stats(source)
            stats.failure_count += 1
            stats.consecutive_failures += 1
            stats.last_check = time.monotonic()
            stats.last_error = error
            if stats.state == CircuitState.HALF_OPEN:
                stats.state = CircuitState.OPEN
                stats.opened_at = time.monotonic()
            elif stats.consecutive_failures >= self._threshold:
                stats.state = CircuitState.OPEN
                stats.opened_at = time.monotonic()

    def get_health(self, source: str) -> SourceHealth:
        """Get health status for a single source."""
        with self._lock:
            stats = self._get_stats(source)
            total = stats.success_count + stats.failure_count
            return SourceHealth(
                name=source,
                status=stats.state,
                success_count=stats.success_count,
                failure_count=stats.failure_count,
                consecutive_failures=stats.consecutive_failures,
                avg_latency_ms=(
                    stats.total_latency_ms / stats.success_count
                    if stats.success_count > 0
                    else 0.0
                ),
                last_check=datetime.now() if stats.last_check else None,
                last_error=stats.last_error,
                error_rate=stats.failure_count / total if total > 0 else 0.0,
            )

    def get_report(self, version: str = "", cache_stats: dict | None = None) -> HealthReport:
        """Get aggregated health report."""
        from openquery.sources import list_sources

        sources_list = list_sources()
        health_list: list[SourceHealth] = []

        with self._lock:
            for src in sources_list:
                meta = src.meta()
                stats = self._get_stats(meta.name)
                total = stats.success_count + stats.failure_count
                health_list.append(
                    SourceHealth(
                        name=meta.name,
                        country=meta.country,
                        status=stats.state,
                        success_count=stats.success_count,
                        failure_count=stats.failure_count,
                        consecutive_failures=stats.consecutive_failures,
                        avg_latency_ms=(
                            stats.total_latency_ms / stats.success_count
                            if stats.success_count > 0
                            else 0.0
                        ),
                        last_check=datetime.now() if stats.last_check else None,
                        last_error=stats.last_error,
                        error_rate=stats.failure_count / total if total > 0 else 0.0,
                    )
                )

        healthy = sum(1 for h in health_list if h.status == CircuitState.CLOSED)
        degraded = sum(1 for h in health_list if h.status == CircuitState.HALF_OPEN)
        unavailable = sum(1 for h in health_list if h.status == CircuitState.OPEN)

        overall = "ok"
        if unavailable > 0:
            overall = "degraded"
        if unavailable > len(health_list) // 2:
            overall = "critical"

        return HealthReport(
            status=overall,
            version=version,
            total_sources=len(health_list),
            healthy=healthy,
            degraded=degraded,
            unavailable=unavailable,
            sources=health_list,
            cache=cache_stats or {},
        )
