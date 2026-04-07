"""BCH Estadísticas data model — Honduras central bank economic statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BchEstadisticasResult(BaseModel):
    """Honduras BCH economic statistics lookup.

    Source: https://www.bch.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    indicator_name: str = ""
    value: str = ""
    period: str = ""
    unit: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
