"""JNE data model — Peru electoral registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JneResult(BaseModel):
    """Voter registration data from Peru's Jurado Nacional de Elecciones.

    Source: https://portal.jne.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dni: str = ""
    nombre: str = ""
    electoral_district: str = ""
    voting_status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
