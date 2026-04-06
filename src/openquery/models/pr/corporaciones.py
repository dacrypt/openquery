"""Department of State corporation registry model — Puerto Rico."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CorporacionesResult(BaseModel):
    """Data from Puerto Rico's Department of State corporation registry.

    Source: https://rcp.estado.pr.gov/en
    """

    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    status: str = ""
    registration_date: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
