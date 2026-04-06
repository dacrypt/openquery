"""FATF high-risk jurisdictions data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntlFatfResult(BaseModel):
    """FATF high-risk jurisdictions lookup result.

    Source: https://www.fatf-gafi.org/en/countries/black-and-grey-lists.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country: str = ""
    list_type: str = ""  # "black", "grey", "none", or "all" for full list
    last_updated: str = ""
    black_list: list[str] = Field(default_factory=list)
    grey_list: list[str] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
