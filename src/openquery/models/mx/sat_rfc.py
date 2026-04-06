"""SAT RFC data model — Mexican RFC validator."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SatRfcResult(BaseModel):
    """RFC validity result from Mexico's SAT RFC validator.

    Source: https://agsc.siat.sat.gob.mx/PTSC/ValidaRFC/index.jsf
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rfc: str = ""
    taxpayer_name: str = ""
    rfc_status: str = ""  # "Activo", "Cancelado", "No inscrito", etc.
    registration_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
