"""El Salvador TSE data model — electoral registry / DUI lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SvTseResult(BaseModel):
    """El Salvador TSE electoral registry lookup result.

    Source: https://consulta.tse.gob.sv/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dui: str = ""
    nombre: str = ""
    centro_votacion: str = ""
    municipio: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
