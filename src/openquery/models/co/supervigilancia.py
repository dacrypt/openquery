"""Supervigilancia private security companies data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SupervigilanciaResult(BaseModel):
    """Supervigilancia private security company registry lookup.

    Source: https://www.supervigilancia.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
