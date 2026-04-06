"""SOAT data model — Peru mandatory vehicle insurance (APESEG/SBS)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SoatResult(BaseModel):
    """SOAT (mandatory insurance) record from Peru's APESEG.

    Source: https://www.apeseg.org.pe/consultas-soat/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    soat_valid: bool = False
    insurer: str = ""
    expiration_date: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
