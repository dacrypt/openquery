"""SUTRAN transport companies data model — Peru."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SutranEmpresasResult(BaseModel):
    """SUTRAN transport company license lookup.

    Source: https://www.sutran.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
