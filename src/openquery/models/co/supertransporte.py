"""SuperTransporte regulated entities data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SupertransporteResult(BaseModel):
    """SuperTransporte transport company lookup.

    Source: https://www.supertransporte.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
