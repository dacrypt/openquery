"""Puerto Rico OATRH government employee verification model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PrOatrhResult(BaseModel):
    """Data from Puerto Rico OATRH government employee registry.

    Source: https://www.oatrh.pr.gov/
    """

    search_term: str = ""
    employee_name: str = ""
    agency: str = ""
    status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
