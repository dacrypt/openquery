"""SUI electricity tariffs data model — live data from Superservicios."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SuiTarifa(BaseModel):
    """Individual tariff record from SUI."""

    operador: str = ""
    estrato: str = ""
    periodo: str = ""
    valor_kwh: str = ""
    componente_generacion: str = ""
    componente_transmision: str = ""
    componente_distribucion: str = ""
    componente_comercializacion: str = ""
    componente_perdidas: str = ""
    componente_restricciones: str = ""


class SuiTarifasResult(BaseModel):
    queried_at: datetime = Field(default_factory=datetime.now)
    ciudad: str = ""
    operador: str = ""
    estrato: str = ""
    total: int = 0
    tarifas: list[SuiTarifa] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
