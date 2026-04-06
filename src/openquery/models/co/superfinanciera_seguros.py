"""Superfinanciera insurance companies data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SuperfinancieraSegurosResult(BaseModel):
    """Superfinanciera insurance entities lookup.

    Source: https://www.superfinanciera.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    entity_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
