"""SUBTEL telecom operator data model — Chile."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SubtelResult(BaseModel):
    """SUBTEL licensed telecom operator lookup.

    Source: https://www.subtel.gob.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    operator_name: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
