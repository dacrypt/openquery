"""Cámara de Comercio de Medellín data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExpedienteMedellin(BaseModel):
    """Single business registration record from Cámara de Comercio de Medellín."""

    matricula: str = ""
    razon_social: str = ""
    estado: str = ""
    tipo: str = ""  # "Persona Natural", "Persona Jurídica", "Establecimiento"
    fecha_matricula: str = ""


class CamaraComercioMedellinResult(BaseModel):
    """Business registry result from Cámara de Comercio de Medellín para Antioquia.

    Source: https://tramites.camaramedellin.com.co/tramites-virtuales/consulta-de-expedientes
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    tipo_busqueda: str = ""  # "nit" or "nombre"
    expedientes: list[ExpedienteMedellin] = Field(default_factory=list)
    total_expedientes: int = 0
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
