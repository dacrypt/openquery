"""Nombre Completo data model — Colombian full name lookup by document."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NombreCompletoResult(BaseModel):
    """Full name lookup by document number.

    Source: Registraduría / RUNT / public databases
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre_completo: str = ""
    primer_nombre: str = ""
    segundo_nombre: str = ""
    primer_apellido: str = ""
    segundo_apellido: str = ""
    encontrado: bool = False
    fuente: str = ""  # Which source provided the name
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
