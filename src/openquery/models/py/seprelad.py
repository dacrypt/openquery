"""SEPRELAD data model — Paraguay money laundering prevention registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SepreladResult(BaseModel):
    """Paraguay SEPRELAD PEP/sanctions registry lookup.

    Source: https://www.seprelad.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    found: bool = False
    entity_name: str = ""
    list_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
