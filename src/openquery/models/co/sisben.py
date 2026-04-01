"""SISBEN data model — Colombian socioeconomic classification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SisbenResult(BaseModel):
    """SISBEN lookup results.

    Source: https://www.sisben.gov.co/Paginas/consulta-tu-grupo.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    grupo: str = ""  # A1-A5, B1-B7, C1-C18, D1-D21
    subgrupo: str = ""
    departamento: str = ""
    municipio: str = ""
    ficha: str = ""
    puntaje: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
