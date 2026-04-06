"""INDECOPI data model — Peruvian trademark and patent search."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IndecopiResult(BaseModel):
    """Trademark/patent record from Peru's INDECOPI (Instituto Nacional de Defensa de la
    Competencia y de la Protección de la Propiedad Intelectual).

    Source: https://www.indecopi.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    trademark_name: str = ""
    owner: str = ""
    status: str = ""
    registration_date: str = ""
    classes: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
