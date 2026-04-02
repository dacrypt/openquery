"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from openquery import __version__
from openquery.models.health import HealthReport
from openquery.server.deps import get_cache, get_health_monitor

router = APIRouter()


@router.get("/health")
async def health():
    """Health check with cache stats."""
    cache = get_cache()
    monitor = get_health_monitor()
    report = monitor.get_report(version=__version__, cache_stats=cache.stats())
    return {
        "status": report.status,
        "version": __version__,
        "sources_total": report.total_sources,
        "sources_healthy": report.healthy,
        "sources_degraded": report.degraded,
        "sources_unavailable": report.unavailable,
        "cache": cache.stats(),
    }


@router.get("/sources/health", response_model=HealthReport)
async def sources_health():
    """Detailed per-source health status."""
    cache = get_cache()
    monitor = get_health_monitor()
    return monitor.get_report(version=__version__, cache_stats=cache.stats())
