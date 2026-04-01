"""Empresas Google data model — business search via Google Maps scraping."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EmpresaGoogle(BaseModel):
    """Single business result from Google Maps."""

    nombre: str = ""
    direccion: str = ""
    telefono: str = ""
    rating: str = ""
    total_resenas: str = ""
    categoria: str = ""
    horario: str = ""
    sitio_web: str = ""


class EmpresasGoogleResult(BaseModel):
    """Google Maps business search result.

    Source: https://www.google.com/maps
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    ubicacion: str = ""
    empresas: list[EmpresaGoogle] = Field(default_factory=list)
    total_empresas: int = 0
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
