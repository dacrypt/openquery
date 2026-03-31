"""Common response models shared across all sources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QueryResult(BaseModel):
    """Universal response envelope for all source queries."""

    ok: bool = True
    source: str = ""
    queried_at: datetime = Field(default_factory=datetime.now)
    cached: bool = False
    latency_ms: int = 0
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    detail: str | None = None
    retryable: bool = False
