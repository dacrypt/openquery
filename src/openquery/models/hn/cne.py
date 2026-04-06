"""Honduras CNE data model — electoral registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnCneResult(BaseModel):
    """Honduras CNE electoral registry lookup result.

    Source: https://censo.cne.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dni: str = ""
    nombre: str = ""
    centro_votacion: str = ""
    distrito: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
