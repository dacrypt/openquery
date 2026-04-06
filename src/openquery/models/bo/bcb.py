"""BCB central bank exchange rates data model — Bolivia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BcbResult(BaseModel):
    """BCB (Banco Central de Bolivia) exchange rate lookup.

    Source: https://www.bcb.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    usd_rate: str = ""
    date: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
