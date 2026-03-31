"""Estaciones EV (EV charging stations) data model — Colombian electric vehicle charging."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EstacionEVResult(BaseModel):
    """EV charging station data from Colombia's datos.gov.co open data portal.

    Source: https://www.datos.gov.co/resource/qqm3-dw2u.json
    """

    ciudad: str = ""
    estaciones: list[dict] = Field(default_factory=list)
    total: int = 0
    audit: Any | None = Field(default=None, exclude=True)
