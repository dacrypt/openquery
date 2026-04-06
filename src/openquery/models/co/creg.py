"""CREG energy regulator data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CregResult(BaseModel):
    """CREG regulated energy entities lookup.

    Source: https://www.creg.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    regulation_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
