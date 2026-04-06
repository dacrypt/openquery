"""SEDES data model — Bolivian health establishments registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SedesResult(BaseModel):
    """SEDES (Servicio Departamental de Salud) health establishments registry (Bolivia).

    Source: https://www.minsalud.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    establishment_name: str = ""
    permit_status: str = ""
    department: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
