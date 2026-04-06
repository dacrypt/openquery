"""Autoridad Fiscalizacion data model — Bolivia business supervision."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BoAutoridadFiscalizacionResult(BaseModel):
    """Bolivia AEMP business registration status.

    Source: https://www.aemp.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
