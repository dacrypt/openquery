"""Bolivia DDRR property registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DdrrResult(BaseModel):
    """Bolivia Derechos Reales property registry lookup result.

    Source: https://magistratura.organojudicial.gob.bo/consultaddrr/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    folio: str = ""
    owner: str = ""
    property_type: str = ""
    liens: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
