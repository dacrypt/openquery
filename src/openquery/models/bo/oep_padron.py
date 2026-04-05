"""Bolivia OEP electoral registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OepPadronResult(BaseModel):
    """Bolivia OEP electoral registry lookup result.

    Source: https://yoparticipo.oep.org.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    departamento: str = ""
    municipio: str = ""
    recinto: str = ""
    mesa: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
