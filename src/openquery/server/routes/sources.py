"""Sources listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from openquery.sources import list_sources

router = APIRouter()


@router.get("/sources")
async def sources_list():
    """List all available data sources."""
    return {
        "sources": [
            {
                "name": src.meta().name,
                "display_name": src.meta().display_name,
                "description": src.meta().description,
                "country": src.meta().country,
                "url": src.meta().url,
                "supported_inputs": src.meta().supported_inputs,
                "requires_captcha": src.meta().requires_captcha,
                "rate_limit_rpm": src.meta().rate_limit_rpm,
            }
            for src in list_sources()
        ]
    }
