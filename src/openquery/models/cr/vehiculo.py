"""Costa Rica vehicle registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrVehiculoResult(BaseModel):
    """Costa Rica vehicle registry lookup result.

    Source: https://ticaconsultas.hacienda.go.cr/Tica/hrgvehiculos.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    owner: str = ""
    brand: str = ""
    model: str = ""
    year: str = ""
    engine: str = ""
    use_type: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
