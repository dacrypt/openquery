"""Tennessee motor vehicle lien search data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TnLienRecord(BaseModel):
    """Individual lien record."""

    document_number: str = ""
    debtor_name: str = ""
    lienholder: str = ""
    filing_date: str = ""
    status: str = ""


class TnLienResult(BaseModel):
    """Tennessee motor vehicle temporary lien search result.

    Source: https://tncab.tnsos.gov/portal/mvtl-search
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    search_type: str = ""  # "vin", "debtor", or "document"
    total_liens: int = 0
    liens: list[TnLienRecord] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
