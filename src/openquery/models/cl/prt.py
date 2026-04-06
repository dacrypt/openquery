"""PRT data model — Vehicle technical inspection status (Chile)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrtResult(BaseModel):
    """Vehicle technical inspection (Revisión Técnica) status from Chile's PRT.

    Source: https://www.prt.cl/Paginas/RevisionTecnica.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    rt_valid: bool | None = None
    expiration_date: str = ""
    last_result: str = ""
    inspection_plant: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
