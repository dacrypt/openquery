"""Fasecolda data model — Colombian vehicle reference prices."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FasecoldaResult(BaseModel):
    """Vehicle reference prices from Fasecolda Guía de Valores.

    Source: https://guiadevalores.fasecolda.com/ConsultaExplorador/
    """

    marca: str = ""
    linea: str = ""
    modelo: int = 0          # year
    valor: int = 0           # reference price COP
    cilindraje: int = 0
    combustible: str = ""
    transmision: str = ""
    puertas: int = 0
    pasajeros: int = 0
    codigo_fasecolda: str = ""
    resultados: list[dict] = Field(default_factory=list)

    audit: Any | None = Field(default=None, exclude=True)
