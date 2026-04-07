"""Justicia data model — Puerto Rico Department of Justice registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrJusticiaResult(BaseModel):
    """Puerto Rico Department of Justice legal entity registry lookup.

    Source: https://www.justicia.pr.gov/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
