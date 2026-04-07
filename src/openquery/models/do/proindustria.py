"""PROINDUSTRIA data model — Dominican Republic industrial registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProindustriaResult(BaseModel):
    """Dominican Republic PROINDUSTRIA industrial registration lookup.

    Source: https://www.proindustria.gob.do/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_number: str = ""
    industry_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
