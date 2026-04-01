"""Libreta Militar data model — Colombian military service status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LibretaMilitarResult(BaseModel):
    """Military service card / situation status.

    Source: https://www.libretamilitar.mil.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    situacion_militar: str = ""  # "Definida", "No definida", etc.
    clase_libreta: str = ""  # "Primera", "Segunda"
    numero_libreta: str = ""
    distrito_militar: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
