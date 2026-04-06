"""Chile SII boleta data model — invoice/boleta verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SiiBoletaResult(BaseModel):
    """SII boleta/invoice verification result.

    Source: https://www.sii.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    folio: str = ""
    boleta_valid: bool = False
    amount: str = ""
    date: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
