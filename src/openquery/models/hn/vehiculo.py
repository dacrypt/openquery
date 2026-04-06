"""Honduras vehicle registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnVehiculoResult(BaseModel):
    """Honduras vehicle registry lookup result.

    Source: https://placas.ip.gob.hn/vehiculos
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    matricula_fee: str = ""
    registration_status: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
