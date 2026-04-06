"""Honduras SEFIN government budget/transparency model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HnSefinResult(BaseModel):
    """Data from Honduras SEFIN budget transparency portal.

    Source: https://www.sefin.gob.hn/
    """

    search_term: str = ""
    entity_name: str = ""
    budget_amount: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
