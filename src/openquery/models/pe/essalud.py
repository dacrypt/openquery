"""Peru EsSalud data model — health insurance affiliation lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EssaludResult(BaseModel):
    """EsSalud health insurance affiliation lookup result.

    Source: https://ww1.essalud.gob.pe/sisep/postulante/postulante_acredita.htm
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dni: str = ""
    affiliation_status: str = ""
    employer: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
