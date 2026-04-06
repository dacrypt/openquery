"""SISBEN Consulta data model — Colombian social targeting system."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SisbenConsultaResult(BaseModel):
    """SISBEN social targeting system result.

    Source: https://www.sisben.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    grupo: str = ""
    subgrupo: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
