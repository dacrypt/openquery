"""Recalls data model — Colombian vehicle safety recalls (SIC)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RecallResult(BaseModel):
    """Vehicle safety recall data from SIC (Superintendencia de Industria y Comercio).

    Source: https://sedeelectronica.sic.gov.co/temas/proteccion-al-consumidor/consumo-seguro/campanas-de-seguridad/automotores
    """

    marca: str = ""
    modelo: str = ""
    total_campanias: int = 0
    campanias: list[dict] = Field(default_factory=list)

    audit: Any | None = Field(default=None, exclude=True)
