"""SOI data model — Colombian social security payment."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SoiPago(BaseModel):
    """A social security payment record."""

    periodo: str = ""
    aportante: str = ""
    tipo_aportante: str = ""
    salud: str = ""
    pension: str = ""
    riesgos: str = ""
    estado: str = ""


class SoiResult(BaseModel):
    """SOI social security payment records.

    Source: https://www.soi.com.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    total_pagos: int = 0
    pagos: list[SoiPago] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
