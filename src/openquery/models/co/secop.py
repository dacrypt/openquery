"""SECOP data model — Colombian public procurement portal."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SecopContrato(BaseModel):
    """A SECOP public contract record."""

    proceso: str = ""
    entidad: str = ""
    objeto: str = ""
    tipo_contrato: str = ""
    valor: str = ""
    estado: str = ""
    fecha_firma: str = ""


class SecopResult(BaseModel):
    """SECOP public procurement results.

    Source: https://www.datos.gov.co/resource/jbjy-vk9h.json (SECOP II)
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre_proveedor: str = ""
    total_contratos: int = 0
    contratos: list[SecopContrato] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
