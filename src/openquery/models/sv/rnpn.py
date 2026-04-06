"""RNPN data model — El Salvador civil registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RnpnResult(BaseModel):
    """El Salvador RNPN civil registry lookup.

    Source: https://www.rnpn.gob.sv/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dui: str = ""
    nombre: str = ""
    civil_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
