"""SEPS data model — Ecuador Superintendencia de Economía Popular y Solidaria."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SepsResult(BaseModel):
    """Organization data from Ecuador's SEPS.

    Source: https://www.seps.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    organization_name: str = ""
    ruc: str = ""
    status: str = ""
    organization_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
