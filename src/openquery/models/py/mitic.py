"""Paraguay MITIC open data portal model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PyMiticDataset(BaseModel):
    """A single dataset entry from datos.gov.py."""

    id: str = ""
    title: str = ""
    name: str = ""
    notes: str = ""
    organization: str = ""
    url: str = ""


class PyMiticResult(BaseModel):
    """Paraguay MITIC government open data portal result.

    Source: https://www.datos.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total_results: int = 0
    datasets: list[PyMiticDataset] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
