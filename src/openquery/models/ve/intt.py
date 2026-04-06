"""INTT data model — Venezuela vehicle registration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InttResult(BaseModel):
    """Venezuela vehicle registration lookup via INTT.

    Source: https://www.intt.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    vehicle_description: str = ""
    registration_status: str = ""
    owner: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
