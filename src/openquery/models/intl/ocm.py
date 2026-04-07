"""Open Charge Map data model — global EV charging station locations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OcmConnector(BaseModel):
    """A connector type at an EV charging station."""

    connector_type: str = ""
    power_kw: float = 0.0
    voltage: int = 0
    amps: int = 0
    current_type: str = ""


class OcmStation(BaseModel):
    """An EV charging station from Open Charge Map."""

    name: str = ""
    operator: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    num_points: int = 0
    status: str = ""
    usage_type: str = ""
    connectors: list[OcmConnector] = Field(default_factory=list)


class OcmResult(BaseModel):
    """Open Charge Map search result.

    Source: https://api.openchargemap.io/v3/poi/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_params: str = ""
    total_stations: int = 0
    stations: list[OcmStation] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
