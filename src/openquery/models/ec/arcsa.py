"""ARCSA data model — Ecuador health product registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ArcsaResult(BaseModel):
    """Sanitary registration data from Ecuador's ARCSA.

    Source: https://www.controlsanitario.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    product_name: str = ""
    registration_number: str = ""
    status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
