"""Dominican Republic DGII placas data model — vehicle plate lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DoPlacasResult(BaseModel):
    """Dominican Republic DGII vehicle plate lookup result.

    Source: https://dgii.gov.do/vehiculosMotor/consultas/Paginas/consultaPlacas.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    owner: str = ""
    plate_status: str = ""
    vehicle_description: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
