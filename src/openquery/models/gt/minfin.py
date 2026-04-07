"""MINFIN data model — Guatemala ministry of finance budget data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MinfinResult(BaseModel):
    """Guatemala MINFIN tax and budget data lookup.

    Source: https://www.minfin.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    budget_amount: str = ""
    fiscal_year: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
