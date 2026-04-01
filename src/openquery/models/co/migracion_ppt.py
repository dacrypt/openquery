"""Migración PPT data model — Permiso por Protección Temporal."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MigracionPptResult(BaseModel):
    """PPT (Permiso por Protección Temporal) status.

    Source: https://www.migracioncolombia.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    tiene_ppt: bool = False
    estado_ppt: str = ""  # "Vigente", "Vencido", "En trámite", etc.
    fecha_expedicion: str = ""
    fecha_vencimiento: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
