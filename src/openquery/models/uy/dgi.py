"""Uruguay DGI data model — tax/RUT lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UyDgiResult(BaseModel):
    """Uruguay DGI tax/RUT lookup result.

    Source: https://servicios.dgi.gub.uy/serviciosenlinea
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    contributor_status: str = ""
    rut_valid: str = ""
    tax_compliance: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
