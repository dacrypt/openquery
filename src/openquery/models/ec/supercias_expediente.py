"""Supercias Expediente data model — Ecuador corporate filings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SuperciasExpedienteResult(BaseModel):
    """Corporate filings from Ecuador's Superintendencia de Compañías.

    Source: https://www.supercias.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    ruc: str = ""
    total_filings: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
