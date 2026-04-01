"""Seguridad Social data model — Colombian social security summary."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AfiliacionSS(BaseModel):
    """A social security affiliation record."""

    tipo: str = ""  # "Salud", "Pensión", "Riesgos Laborales", "Caja Compensación"
    administradora: str = ""
    estado: str = ""
    regimen: str = ""


class SeguridadSocialResult(BaseModel):
    """Social security summary (health, pension, labor risks, compensation fund).

    Source: Various PILA/SOI/RUAF portals
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    afiliaciones: list[AfiliacionSS] = Field(default_factory=list)
    cotizante_activo: bool = False
    ultimo_periodo_pagado: str = ""
    empleador: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
