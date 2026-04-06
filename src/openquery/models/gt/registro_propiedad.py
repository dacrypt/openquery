"""Guatemala property registry model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtRegistroPropiedadResult(BaseModel):
    """Guatemala property registry result.

    Source: https://eregistros.registromercantil.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    finca_number: str = ""
    owner: str = ""
    property_type: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
