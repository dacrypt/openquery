"""IGAC data model — Colombian catastro/property registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IgacResult(BaseModel):
    """IGAC (Instituto Geografico Agustin Codazzi) catastro property registry (Colombia).

    Source: https://www.igac.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cadastral_code: str = ""
    owner: str = ""
    area: str = ""
    land_use: str = ""
    valuation: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
