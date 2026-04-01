"""NUPTSE data model — Colombian electricity market operator."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TarifaEnergia(BaseModel):
    """An electricity tariff record."""

    estrato: str = ""
    componente: str = ""
    valor_kwh: str = ""
    empresa: str = ""
    departamento: str = ""
    municipio: str = ""


class NuptseResult(BaseModel):
    """Electricity tariff data from SUI/SSPD.

    Source: https://www.datos.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    tarifas: list[TarifaEnergia] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
