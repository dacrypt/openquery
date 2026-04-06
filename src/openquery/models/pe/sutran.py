"""SUTRAN data model — Peru traffic infraction record by plate."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SutranInfraction(BaseModel):
    """A single SUTRAN traffic infraction."""

    type: str = ""
    date: str = ""
    amount: str = ""
    status: str = ""


class SutranResult(BaseModel):
    """Traffic infraction record from Peru's SUTRAN.

    Source: https://www.sutran.gob.pe/consultas/record-de-infracciones/record-de-infracciones/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    total_infractions: int = 0
    infractions: list[SutranInfraction] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
