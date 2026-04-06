"""AFIP Monotributo data model — Argentina monotributo status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AfipMonotributoResult(BaseModel):
    """Monotributo category and status from Argentina's AFIP.

    Source: https://www.afip.gob.ar/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cuit: str = ""
    taxpayer_name: str = ""
    category: str = ""
    status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
