"""Argentina SISA REFES data model — health facility registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SisaRefesResult(BaseModel):
    """Health facility info from Argentina's SISA REFES registry.

    Source: https://sisa.msal.gov.ar/sisa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    facility_name: str = ""
    facility_type: str = ""
    cuit: str = ""
    address: str = ""
    province: str = ""
    sector: str = ""
    services: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
