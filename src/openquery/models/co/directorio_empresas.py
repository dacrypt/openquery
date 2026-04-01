"""Directorio de Empresas data model — Colombian business directory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EmpresaDirectorio(BaseModel):
    """Single business entry from the directory."""

    razon_social: str = ""
    nit: str = ""
    actividad_economica: str = ""
    ciiu: str = ""
    direccion: str = ""
    municipio: str = ""
    departamento: str = ""
    telefono: str = ""
    estado: str = ""


class DirectorioEmpresasResult(BaseModel):
    """Business directory lookup result.

    Source: datos.gov.co / Confecámaras open data
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    tipo_busqueda: str = ""  # "nit" or "nombre"
    empresas: list[EmpresaDirectorio] = Field(default_factory=list)
    total_empresas: int = 0
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
