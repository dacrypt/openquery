"""DINARDAP data model — Ecuador identity and property lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DinardapResult(BaseModel):
    """Identity and property data from Ecuador's DINARDAP.

    Source: https://www.dinardap.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    property_records: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
