"""Ecuador SRI Establecimientos data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Establecimiento(BaseModel):
    """An establishment from SRI RUC lookup."""

    nombre_fantasia: str = ""
    tipo: str = ""
    direccion: str = ""
    estado: str = ""
    numero: str = ""


class EcSriEstablecimientosResult(BaseModel):
    """Ecuador SRI establishments lookup result.

    Source: https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/Establecimiento/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ruc: str = ""
    total: int = 0
    establecimientos: list[Establecimiento] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
