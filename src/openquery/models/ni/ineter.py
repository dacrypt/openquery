"""Nicaragua INETER property/cadastro model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiIneterResult(BaseModel):
    """Nicaragua INETER cadastral data result.

    Source: https://www.ineter.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    property_code: str = ""
    owner: str = ""
    location: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
