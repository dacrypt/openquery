"""RPPDF data model — CDMX property registry (Mexico)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RppdfResult(BaseModel):
    """RPPDF (Registro Publico de la Propiedad del Distrito Federal) property registry (Mexico).

    Source: https://www.sedatu.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    folio: str = ""
    owner: str = ""
    property_type: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
