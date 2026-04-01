"""SUNARP Vehicular data model — Peruvian vehicle registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SunarpVehicularResult(BaseModel):
    """Vehicle registration from Peru's SUNARP.

    Source: https://consultavehicular.sunarp.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    propietario: str = ""
    marca: str = ""
    modelo: str = ""
    anio: str = ""
    color: str = ""
    vin: str = ""
    estado: str = ""
    audit: Any | None = Field(default=None, exclude=True)
