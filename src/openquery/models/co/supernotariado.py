"""Supernotariado data model — Colombian notary registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SupernotariadoResult(BaseModel):
    """Supernotariado notary registry result.

    Source: https://www.supernotariado.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    notary_name: str = ""
    city: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
