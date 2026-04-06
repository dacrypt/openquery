"""BCV data model — Venezuela Central Bank exchange rates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BcvResult(BaseModel):
    """Venezuela Central Bank official exchange rates.

    Source: https://www.bcv.org.ve/estadisticas/tipo-de-cambio-de-referencia
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    usd_rate: str = ""
    eur_rate: str = ""
    cny_rate: str = ""
    try_rate: str = ""
    rub_rate: str = ""
    date: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
