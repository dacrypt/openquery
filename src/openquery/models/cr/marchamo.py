"""Costa Rica INS marchamo (vehicle insurance/tax) data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrMarchamoResult(BaseModel):
    """Costa Rica INS marchamo and SOA insurance lookup result.

    Source: https://marchamo.ins-cr.com/marchamo/ConsultaMarchamo.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    marchamo_amount: str = ""
    marchamo_expiry: str = ""
    insurance_status: str = ""
    vehicle_description: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
