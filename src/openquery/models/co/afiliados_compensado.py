"""Afiliados Compensados data model — Colombian compensation fund affiliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AfiliadosCompensadoResult(BaseModel):
    """Compensation fund (Caja de Compensación) affiliation status.

    Source: Various compensation fund portals
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    esta_afiliado: bool = False
    caja_compensacion: str = ""
    estado: str = ""
    categoria: str = ""
    empresa: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
