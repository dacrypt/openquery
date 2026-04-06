"""Costa Rica TSE electoral registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrTseResult(BaseModel):
    """Costa Rica TSE cedula/electoral registry lookup result.

    Source: https://servicioselectorales.tse.go.cr/chc/consulta_cedula.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    genero: str = ""
    distrito: str = ""
    fecha_vencimiento: str = ""
    precinto: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
