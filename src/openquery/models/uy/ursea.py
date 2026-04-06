"""URSEA energy/water regulator data model — Uruguay."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UrseaResult(BaseModel):
    """URSEA regulated energy/water entity lookup.

    Source: https://www.gub.uy/unidad-reguladora-servicios-energia-agua/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    regulation_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
