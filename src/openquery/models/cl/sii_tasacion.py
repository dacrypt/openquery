"""SII Tasacion data model — Vehicle tax valuation (Chile)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SiiTasacionResult(BaseModel):
    """Vehicle tax valuation from Chile's SII (Servicio de Impuestos Internos).

    Used for permiso de circulacion calculation.
    Source: https://www4.sii.cl/vehiculospubui/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    tasacion_value: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
