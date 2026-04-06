"""RENIEC data model — Peruvian national identity registry (DNI)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReniecResult(BaseModel):
    """Identity record from Peru's RENIEC (Registro Nacional de Identificación y Estado Civil).

    Source: https://eldni.com/pe/buscar-por-dni
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dni: str = ""
    nombre: str = ""
    apellido_paterno: str = ""
    apellido_materno: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
