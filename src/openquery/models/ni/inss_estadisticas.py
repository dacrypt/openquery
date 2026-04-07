"""INSS Estadísticas data model — Nicaragua social security statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InssEstadisticasResult(BaseModel):
    """Nicaragua INSS social security statistics lookup.

    Source: https://www.inss.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    indicator_name: str = ""
    value: str = ""
    period: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
