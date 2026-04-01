"""Pico y Placa data model — Colombian driving restriction lookup."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PicoYPlacaResult(BaseModel):
    """Driving restriction status for a vehicle plate in Colombian cities.

    Pure logic — no external API needed.
    """

    placa: str = ""
    ultimo_digito: str = ""
    ciudad: str = ""
    ciudad_nombre: str = ""  # Full display name
    fecha: str = ""          # ISO date queried
    restringido: bool = False
    horario: str = ""        # restriction hours
    motivo: str = ""         # why restricted or not
    tipo_vehiculo: str = ""  # particular, taxi, etc
    exento: bool = False     # EV/hybrid exempt
    fuente_oficial: str = "" # URL of official source
    vigencia: str = ""       # validity period of the rule

    audit: Any | None = Field(default=None, exclude=True)
