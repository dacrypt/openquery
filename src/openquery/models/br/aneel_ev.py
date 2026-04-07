"""ANEEL EV charging station data model — Brazil EV station registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AneelEvStation(BaseModel):
    """An EV charging station from the ANEEL registry."""

    name: str = ""
    operator: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    power_kw: str = ""
    connector_type: str = ""
    public_access: str = ""


class AneelEvResult(BaseModel):
    """ANEEL EV charging station search result.

    Source: https://dadosabertos.aneel.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_params: str = ""
    total_stations: int = 0
    stations: list[AneelEvStation] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
