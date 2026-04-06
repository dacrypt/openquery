"""Conservador data model — Chile property registry (Conservador de Bienes Raíces)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConservadorResult(BaseModel):
    """Property records from Chile's Conservador de Bienes Raíces.

    Source: https://conservador.cl/portal/consultas_en_linea
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    property_records: list[dict[str, Any]] = Field(default_factory=list)
    mortgages: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
