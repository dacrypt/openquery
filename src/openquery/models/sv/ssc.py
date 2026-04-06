"""El Salvador SSC social security (AFP/ISSS) model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SscResult(BaseModel):
    """SSC social security affiliation result for El Salvador.

    Source: https://www.ssc.gob.sv/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dui: str = ""
    affiliation_status: str = ""
    afp: str = ""  # Administradora de Fondos de Pensiones
    isss: str = ""  # Instituto Salvadoreño del Seguro Social
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
