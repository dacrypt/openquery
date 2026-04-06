"""Uruguay Corte Electoral data model — voter registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UyCorteElectoralResult(BaseModel):
    """Uruguay Corte Electoral voter registry result.

    Source: https://aplicaciones.corteelectoral.gub.uy/buscadorpermanente/buscadores.buscadorpermanente.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    credencial: str = ""
    nombre: str = ""
    habilitado: str = ""
    lugar_votacion: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
