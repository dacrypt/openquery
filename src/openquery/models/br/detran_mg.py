"""Brazil DETRAN-MG data model — Minas Gerais vehicle lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DetranMgResult(BaseModel):
    """Minas Gerais DETRAN vehicle lookup result.

    Source: https://detran.mg.gov.br/veiculos
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    renavam: str = ""
    vehicle_description: str = ""
    situation: str = ""
    ipva_status: str = ""
    total_debt: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
