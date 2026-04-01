"""Retención de Vehículos data model — Colombian impounded vehicles."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RetencionVehiculosResult(BaseModel):
    """Impounded/retained vehicles lookup.

    Source: Various transit authority portals
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    esta_retenido: bool = False
    patio: str = ""
    fecha_retencion: str = ""
    autoridad: str = ""
    motivo: str = ""
    estado: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
