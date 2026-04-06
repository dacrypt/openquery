"""Nicaragua DGR data model — tax rates registry (Dirección General de Rentas)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiDgrResult(BaseModel):
    """Nicaragua DGR taxpayer registration lookup result.

    Source: https://www.dgi.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    taxpayer_name: str = ""
    tax_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
