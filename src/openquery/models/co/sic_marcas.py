"""SIC Marcas data model — Colombian trademark registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SicMarcasResult(BaseModel):
    """SIC trademark registry result.

    Source: https://www.sic.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    trademark_name: str = ""
    owner: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
