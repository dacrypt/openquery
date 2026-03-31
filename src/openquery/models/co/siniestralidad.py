"""Siniestralidad (road crash hotspots) data model — Colombian road safety data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SiniestralidadResult(BaseModel):
    """Road crash hotspot data from Colombia's datos.gov.co open data portal.

    Source: https://www.datos.gov.co/resource/rs3u-8r4q.json
    """

    departamento: str = ""
    municipio: str = ""
    sectores: list[dict] = Field(default_factory=list)
    total_sectores: int = 0
    total_fallecidos: int = 0
    audit: Any | None = Field(default=None, exclude=True)
