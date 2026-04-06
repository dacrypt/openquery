"""Uruguay IMPO legal norms database model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UyImpoNorm(BaseModel):
    """A single IMPO legal norm entry."""

    title: str = ""
    number: str = ""
    date: str = ""
    url: str = ""


class UyImpoResult(BaseModel):
    """Data from Uruguay IMPO legal norms database.

    Source: https://www.impo.com.uy/
    """

    search_term: str = ""
    total_results: int = 0
    norms: list[UyImpoNorm] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
