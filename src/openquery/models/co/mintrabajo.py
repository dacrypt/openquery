"""MinTrabajo labor consultations data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MintrabajoResult(BaseModel):
    """MinTrabajo labor compliance lookup.

    Source: https://www.mintrabajo.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    nit: str = ""
    company_name: str = ""
    compliance_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
