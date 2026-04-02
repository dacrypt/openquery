"""Health monitoring and circuit breaker models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing one request


class SourceHealth(BaseModel):
    """Health status for a single source."""

    name: str
    country: str = ""
    status: CircuitState = CircuitState.CLOSED
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    avg_latency_ms: float = 0.0
    last_check: datetime | None = None
    last_error: str | None = None
    error_rate: float = 0.0


class HealthReport(BaseModel):
    """Aggregated health report for all sources."""

    status: str = "ok"
    version: str = ""
    total_sources: int = 0
    healthy: int = 0
    degraded: int = 0
    unavailable: int = 0
    sources: list[SourceHealth] = Field(default_factory=list)
    cache: dict = Field(default_factory=dict)
