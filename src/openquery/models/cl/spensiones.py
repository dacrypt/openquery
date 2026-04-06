"""Superintendencia de Pensiones data model — Chilean AFP/AFC affiliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SpensionesResult(BaseModel):
    """AFP/AFC affiliation data from Chile's Superintendencia de Pensiones.

    Source: https://www.spensiones.cl/portal/institucional/597/w3-article-15721.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    afp_name: str = ""
    afp_status: str = ""
    afc_status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
