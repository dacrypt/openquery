"""Colombia datos.gov.co catalog data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DatosCatalogoEntry(BaseModel):
    """A dataset from datos.gov.co catalog."""

    nombre: str = ""
    descripcion: str = ""
    entidad: str = ""
    categoria: str = ""
    url: str = ""
    recurso_id: str = ""


class DatosCatalogoResult(BaseModel):
    """Colombia datos.gov.co catalog search result.

    Source: https://www.datos.gov.co/api/catalog/v1
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    datasets: list[DatosCatalogoEntry] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
