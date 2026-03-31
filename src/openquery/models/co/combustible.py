"""Combustible (fuel prices) data model — Colombian gas station prices."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CombustibleResult(BaseModel):
    """Fuel price data from Colombia's datos.gov.co open data portal.

    Source: https://www.datos.gov.co/resource/gjy9-tpph.json
    """

    departamento: str = ""
    municipio: str = ""
    estaciones: list[dict] = Field(default_factory=list)
    total_estaciones: int = 0
    audit: Any | None = Field(default=None, exclude=True)
