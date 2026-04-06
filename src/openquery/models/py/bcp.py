"""Paraguay BCP central bank exchange rates model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PyBcpResult(BaseModel):
    """Paraguay BCP central bank exchange rate result.

    Source: https://www.bcp.gov.py/webapps/web/cotizacion/monedas
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    usd_rate: str = ""
    date: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
