"""MSP Profesionales data model — Uruguayan health professionals registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MspProfesionalesResult(BaseModel):
    """MSP health professionals registration (Uruguay).

    Source: https://www.gub.uy/ministerio-salud-publica/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    professional_name: str = ""
    profession: str = ""
    registration_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
