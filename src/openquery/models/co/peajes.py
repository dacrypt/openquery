"""Peajes (toll tariffs) data model — Colombian toll booth prices."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PeajeResult(BaseModel):
    """Toll tariff data from Colombia's datos.gov.co open data portal.

    Source: https://www.datos.gov.co/resource/7gj8-j6i3.json
    """

    peaje: str = ""
    categoria: str = ""
    valor: int = 0
    fecha_actualizacion: str = ""
    resultados: list[dict] = Field(default_factory=list)
    total: int = 0
    audit: Any | None = Field(default=None, exclude=True)
