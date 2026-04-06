"""CICPC data model — Venezuela criminal records lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CicpcResult(BaseModel):
    """Venezuela CICPC criminal records lookup result.

    Source: https://www.cicpc.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    criminal_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
