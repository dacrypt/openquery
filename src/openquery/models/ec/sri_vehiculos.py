"""SRI Vehiculos data model — Ecuador vehicle tax and registration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SriVehiculosResult(BaseModel):
    """Vehicle tax and registration data from Ecuador's SRI (Servicio de Rentas Internas).

    Source: https://www.sri.gob.ec/impuestos-vehiculares
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    vehicle_description: str = ""
    brand: str = ""
    model: str = ""
    year: str = ""
    impuesto_vehicular: str = ""
    sppat_amount: str = ""
    total_due: str = ""
    registration_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
