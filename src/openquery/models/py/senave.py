"""Paraguay SENAVE phytosanitary registry model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SenaveResult(BaseModel):
    """SENAVE phytosanitary registry result for Paraguay.

    Source: https://www.senave.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
