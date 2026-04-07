"""IHTT data model — Honduras tourism establishment registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IhttResult(BaseModel):
    """Honduras IHTT tourism establishment license lookup.

    Source: https://www.iht.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    establishment_name: str = ""
    establishment_type: str = ""
    license_number: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
