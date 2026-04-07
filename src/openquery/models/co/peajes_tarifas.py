"""Peajes tarifas data model — Colombian toll booth tariffs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CoPeajesTarifasResult(BaseModel):
    """Colombian toll tariffs from datos.gov.co.

    Source: https://www.datos.gov.co/resource/
    """

    peaje: str = ""
    categoria: str = ""
    tarifa: str = ""
    ruta: str = ""
    details: str = ""
    records: list[dict] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=datetime.now)
    audit: Any | None = Field(default=None, exclude=True)
