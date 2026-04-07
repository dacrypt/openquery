"""SENACSA data model — Paraguay animal health registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SenácsaResult(BaseModel):
    """Paraguay SENACSA animal health sanitary registry lookup.

    Source: https://www.senacsa.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    farm_name: str = ""
    owner_name: str = ""
    sanitary_status: str = ""
    registration_number: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
