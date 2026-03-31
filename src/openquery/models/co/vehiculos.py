"""Vehiculos data model — Colombian national vehicle fleet data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VehiculosResult(BaseModel):
    """Vehicle fleet data from Colombia's datos.gov.co open data portal.

    Source: https://www.datos.gov.co/resource/g7i9-xkxz.json
    """

    placa: str = ""
    clase: str = ""          # AUTOMOVIL, CAMIONETA, etc.
    marca: str = ""
    modelo: str = ""         # year as string
    servicio: str = ""       # PARTICULAR, PUBLICO
    cilindraje: int = 0
    resultados: list[dict] = Field(default_factory=list)
    total: int = 0

    audit: Any | None = Field(default=None, exclude=True)
