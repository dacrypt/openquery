"""Brazil DETRAN-RJ data model — Rio de Janeiro vehicle lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DetranRjResult(BaseModel):
    """Rio de Janeiro DETRAN vehicle lookup result.

    Source: https://www.detran.rj.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    renavam: str = ""
    vehicle_description: str = ""
    situation: str = ""
    total_debt: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
