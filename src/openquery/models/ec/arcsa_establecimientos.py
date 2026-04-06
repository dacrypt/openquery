"""ARCSA Establecimientos data model — Ecuadorian health establishments registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ArcsaEstablecimientosResult(BaseModel):
    """ARCSA health establishments and permits registry (Ecuador).

    Source: https://www.controlsanitario.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    establishment_name: str = ""
    permit_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
