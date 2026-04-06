"""CPSC Recalls data model — US product safety recalls."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CpscRecallEntry(BaseModel):
    """A single CPSC product recall entry."""

    title: str = ""
    description: str = ""
    date: str = ""


class CpscRecallsResult(BaseModel):
    """CPSC (Consumer Product Safety Commission) product recalls result.

    Source: https://www.saferproducts.gov/RestWebServices/Recall
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    recalls: list[CpscRecallEntry] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
