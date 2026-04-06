"""Profeco data model — Mexican consumer complaints (Buró Comercial Profeco)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProfecoResult(BaseModel):
    """Consumer complaint data from Mexico's Profeco Buró Comercial.

    Source: https://burocomercial.profeco.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    provider_name: str = ""
    total_complaints: int = 0
    resolved: int = 0
    conciliation_rate: str = ""  # percentage string e.g. "60.0%"
    sector: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
