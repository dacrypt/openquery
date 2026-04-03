"""Panama INEC data model — national statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InecCategoria(BaseModel):
    """A statistics category from INEC."""

    id: str = ""
    nombre: str = ""
    descripcion: str = ""


class PaInecResult(BaseModel):
    """Panama INEC statistics result.

    Source: https://www.inec.gob.pa/m_2/api/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    categorias: list[InecCategoria] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
