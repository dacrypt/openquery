"""Honduras SAR tax registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnSarResult(BaseModel):
    """Honduras SAR RTN/tax lookup result.

    Source: https://www.sar.gob.hn/registro-tributario-nacional-rtn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rtn: str = ""
    taxpayer_name: str = ""
    address: str = ""
    registration_date: str = ""
    tax_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
