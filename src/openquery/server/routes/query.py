"""Universal query endpoint."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from openquery.core.cache import make_key
from openquery.server.deps import get_cache, get_rate_limiter
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput

router = APIRouter()


class QueryRequest(BaseModel):
    """Request body for the universal query endpoint."""

    source: str
    document_type: DocumentType
    document_number: str
    bypass_cache: bool = False


class QueryResponse(BaseModel):
    """Response envelope."""

    ok: bool = True
    source: str = ""
    queried_at: datetime | None = None
    cached: bool = False
    latency_ms: int = 0
    data: dict[str, Any] = {}
    error: str | None = None
    detail: str | None = None
    retryable: bool = False


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Query a data source."""
    start = time.monotonic()
    cache = get_cache()
    limiter = get_rate_limiter()

    # Check cache
    cache_key = make_key(req.source, req.document_type, req.document_number)
    if not req.bypass_cache:
        cached = cache.get(cache_key)
        if cached:
            elapsed = int((time.monotonic() - start) * 1000)
            return QueryResponse(
                source=req.source,
                queried_at=datetime.now(),
                cached=True,
                latency_ms=elapsed,
                data=cached,
            )

    # Get source
    try:
        src = get_source(req.source)
    except KeyError as e:
        return QueryResponse(ok=False, source=req.source, error="unknown_source", detail=str(e))

    # Rate limit
    if not limiter.is_allowed(req.source):
        return QueryResponse(
            ok=False,
            source=req.source,
            error="rate_limited",
            detail=f"Too many requests for {req.source}",
            retryable=True,
        )

    # Execute query
    try:
        result = src.query(QueryInput(
            document_type=req.document_type,
            document_number=req.document_number,
        ))
        data = result.model_dump(mode="json")

        # Cache result
        cache.set(cache_key, data)

        elapsed = int((time.monotonic() - start) * 1000)
        return QueryResponse(
            source=req.source,
            queried_at=datetime.now(),
            latency_ms=elapsed,
            data=data,
        )
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return QueryResponse(
            ok=False,
            source=req.source,
            queried_at=datetime.now(),
            latency_ms=elapsed,
            error=type(e).__name__,
            detail=str(e),
            retryable="captcha" in str(e).lower(),
        )
