"""Panama RUC data model — DGI tax registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaRucResult(BaseModel):
    """Panama RUC lookup result.

    Source: https://dgi.mef.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ruc: str = ""
    nombre: str = ""
    dv: str = ""
    estado: str = ""
    tipo_contribuyente: str = ""
    actividad_economica: str = ""
    direccion: str = ""
    provincia: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
