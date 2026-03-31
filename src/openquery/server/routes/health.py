"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from openquery import __version__
from openquery.server.deps import get_cache

router = APIRouter()


@router.get("/health")
async def health():
    """Health check with cache stats."""
    cache = get_cache()
    return {
        "status": "ok",
        "version": __version__,
        "cache": cache.stats(),
    }
