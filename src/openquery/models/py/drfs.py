"""Paraguay DRFS data model — company registry lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PyDrfsResult(BaseModel):
    """Paraguay DRFS company registry lookup result.

    Source: https://drfs.abogacia.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    folio: str = ""
    company_type: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
