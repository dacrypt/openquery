"""MINGOB security companies data model — Guatemala."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MingobResult(BaseModel):
    """MINGOB private security company license lookup.

    Source: https://www.mingob.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
