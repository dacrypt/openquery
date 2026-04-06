"""Registro Titulos data model — Dominican Republic land titles registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegistroTitulosResult(BaseModel):
    """Land titles registry (Dominican Republic).

    Source: https://ri.gob.do/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    title_status: str = ""
    owner: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
