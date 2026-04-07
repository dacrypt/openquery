"""Combustible precios data model — Colombian fuel prices by city."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CoCombustiblePreciosResult(BaseModel):
    """Colombian fuel prices by city from datos.gov.co.

    Source: https://www.datos.gov.co/resource/
    """

    ciudad: str = ""
    combustible: str = ""
    precio_galon: str = ""
    fecha: str = ""
    details: str = ""
    records: list[dict] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=datetime.now)
    audit: Any | None = Field(default=None, exclude=True)
