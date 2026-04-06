"""SEC EDGAR data model — US company filings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SecEdgarFiling(BaseModel):
    """A single SEC EDGAR filing record."""

    filing_type: str = ""
    date: str = ""
    description: str = ""
    url: str = ""


class SecEdgarResult(BaseModel):
    """SEC EDGAR company filings search result.

    Source: https://efts.sec.gov/LATEST/search-index
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    cik: str = ""
    total_filings: int = 0
    filings: list[SecEdgarFiling] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
