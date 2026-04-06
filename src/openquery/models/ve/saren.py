"""SAREN data model — Venezuela company registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SarenResult(BaseModel):
    """Venezuela company registry lookup.

    Source: https://consultapub.saren.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    rif: str = ""
    registration_status: str = ""
    company_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
