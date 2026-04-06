"""GLEIF data model — Legal Entity Identifier (LEI) registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntlGleifResult(BaseModel):
    """GLEIF LEI lookup result.

    Source: https://api.gleif.org/api/v1/lei-records
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    lei: str = ""
    legal_name: str = ""
    jurisdiction: str = ""
    entity_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
