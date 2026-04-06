"""Guatemala SAT vehicle data model — circulation tax."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtSatVehiculoResult(BaseModel):
    """Guatemala SAT vehicle circulation tax lookup result.

    Source: https://portal.sat.gob.gt/portal/impresion-calcomania/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    nit: str = ""
    tax_amount: str = ""
    payment_status: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
