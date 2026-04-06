"""ICIJ Offshore Leaks database data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IcijOffshoreEntity(BaseModel):
    """A single entity from the ICIJ Offshore Leaks database."""

    node_id: str = ""
    name: str = ""
    entity_type: str = ""
    country: str = ""
    jurisdiction: str = ""
    dataset: str = ""
    url: str = ""


class IcijOffshoreResult(BaseModel):
    """ICIJ Offshore Leaks database search result.

    Source: https://offshoreleaks.icij.org/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    entities: list[IcijOffshoreEntity] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
