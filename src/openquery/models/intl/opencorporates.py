"""OpenCorporates global company search data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OpenCorporatesCompany(BaseModel):
    """A single company record from OpenCorporates."""

    name: str = ""
    jurisdiction: str = ""
    status: str = ""
    company_number: str = ""
    incorporation_date: str = ""
    company_type: str = ""
    registered_address: str = ""


class IntlOpenCorporatesResult(BaseModel):
    """OpenCorporates global company search result.

    Source: https://api.opencorporates.com/v0.4/companies/search
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    companies: list[OpenCorporatesCompany] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
