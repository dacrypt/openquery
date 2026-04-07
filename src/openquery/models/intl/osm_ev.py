"""OpenStreetMap EV charging stations data model — global OSM nodes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OsmEvStation(BaseModel):
    """An EV charging station node from OpenStreetMap."""

    osm_id: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    operator: str = ""
    capacity: str = ""
    socket_types: list[str] = Field(default_factory=list)
    fee: str = ""
    opening_hours: str = ""


class OsmEvResult(BaseModel):
    """OpenStreetMap EV charging station search result.

    Source: https://overpass-api.de/api/interpreter
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_params: str = ""
    total_stations: int = 0
    stations: list[OsmEvStation] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
