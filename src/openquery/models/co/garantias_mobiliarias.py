"""Garantías Mobiliarias data model — Colombian movable collateral registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GarantiaEntry(BaseModel):
    """A movable collateral guarantee entry."""

    numero_registro: str = ""
    tipo_garantia: str = ""
    deudor: str = ""
    acreedor: str = ""
    descripcion_bien: str = ""
    fecha_inscripcion: str = ""
    estado: str = ""


class GarantiasMobiliariasResult(BaseModel):
    """Movable collateral guarantees registry results.

    Source: https://www.garantiasmobiliarias.com.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    tiene_garantias: bool = False
    total_garantias: int = 0
    garantias: list[GarantiaEntry] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
