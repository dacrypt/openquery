"""Common CKAN data model — shared by open data catalog sources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CkanDataset(BaseModel):
    """A dataset from a CKAN open data catalog."""

    id: str = ""
    title: str = ""
    name: str = ""
    notes: str = ""
    organization: str = ""
    num_resources: int = 0
    url: str = ""


class CkanSearchResult(BaseModel):
    """CKAN open data catalog search result."""

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    portal: str = ""
    total: int = 0
    datasets: list[CkanDataset] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
