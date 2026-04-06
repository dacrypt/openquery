"""Honduras RAP data model — property registry (Registro de la Propiedad)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnRapResult(BaseModel):
    """Honduras property registry lookup result.

    Source: https://www.ip.gob.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    owner: str = ""
    property_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
