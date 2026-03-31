"""API key authentication middleware."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from openquery.config import get_settings


def setup_auth(app: FastAPI) -> None:
    """Add API key middleware if OPENQUERY_API_KEY is set."""
    settings = get_settings()
    if not settings.api_key:
        return

    @app.middleware("http")
    async def check_api_key(request: Request, call_next):
        # Skip auth for docs and health
        if request.url.path in ("/docs", "/openapi.json", "/redoc", "/api/v1/health"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "error": "invalid_api_key",
                    "detail": "Missing or invalid API key",
                },
            )
        return await call_next(request)
