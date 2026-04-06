"""SENA Egresados data model — SENA graduate verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SenaEgresadosResult(BaseModel):
    """SENA graduate verification result.

    Source: https://www.sena.edu.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    program: str = ""
    completion_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
