"""Guatemala TSE data model — electoral registry / DPI lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtTseResult(BaseModel):
    """Guatemala TSE electoral registry lookup result.

    Source: https://www.tse.org.gt/reg-ciudadanos/sistema-de-estadisticas/consulta-de-afiliacion
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dpi: str = ""
    nombre: str = ""
    estado_electoral: str = ""
    lugar_votacion: str = ""
    municipio: str = ""
    afiliacion: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
