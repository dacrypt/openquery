"""SERNAC data model — Chile consumer complaints portal."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SernacResult(BaseModel):
    """Consumer complaint statistics from Chile's SERNAC.

    Source: https://www.sernac.cl/portal/619/w3-propertyvalue-62498.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    company_name: str = ""
    total_complaints: str = ""
    resolution_rate: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
