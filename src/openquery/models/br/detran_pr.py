"""Brazil DETRAN-PR data model — Paraná vehicle lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DetranPrResult(BaseModel):
    """Paraná DETRAN vehicle lookup result.

    Source: https://www.detran.pr.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    vehicle_description: str = ""
    situation: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
