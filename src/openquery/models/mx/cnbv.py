"""CNBV data model — Mexico banking supervisor."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CnbvResult(BaseModel):
    """Supervised entity data from Mexico's CNBV.

    Source: https://www.cnbv.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
