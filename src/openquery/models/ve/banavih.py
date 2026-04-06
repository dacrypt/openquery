"""BANAVIH data model — Venezuela housing savings (FAOV)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BanavihResult(BaseModel):
    """Venezuela BANAVIH FAOV housing savings lookup.

    Source: https://www.banavih.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    contribution_status: str = ""
    employer: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
