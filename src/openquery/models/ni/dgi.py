"""Nicaragua DGI data model — tax/RUC registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiDgiResult(BaseModel):
    """Nicaragua DGI taxpayer lookup result.

    Source: https://dgienlinea.dgi.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ruc: str = ""
    taxpayer_name: str = ""
    tax_status: str = ""
    address: str = ""
    economic_activity: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
