"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from openquery import __version__


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OpenQuery API",
        description="Query public data sources worldwide",
        version=__version__,
    )

    # Include routes
    from openquery.server.routes.health import router as health_router
    from openquery.server.routes.query import router as query_router
    from openquery.server.routes.sources import router as sources_router

    app.include_router(health_router, prefix="/api/v1", tags=["system"])
    app.include_router(sources_router, prefix="/api/v1", tags=["system"])
    app.include_router(query_router, prefix="/api/v1", tags=["query"])

    # API key middleware
    from openquery.server.auth import setup_auth
    setup_auth(app)

    return app
