"""SUNAFIL data model — Peruvian labor inspection records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SunafilInspeccion(BaseModel):
    """Single labor inspection record."""

    numero: str = ""
    fecha: str = ""
    materia: str = ""
    resultado: str = ""
    sancion: str = ""


class SunafilResult(BaseModel):
    """Labor inspection records from Peru's SUNAFIL (Superintendencia Nacional de
    Fiscalización Laboral).

    Source: https://www.sunafil.gob.pe/consultas-en-linea.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ruc: str = ""
    employer_name: str = ""
    inspections_count: int = 0
    sanctions: list[str] = Field(default_factory=list)
    inspections: list[SunafilInspeccion] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
