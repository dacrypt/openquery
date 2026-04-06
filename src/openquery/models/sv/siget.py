"""SIGET data model — El Salvador utilities regulator."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SigetResult(BaseModel):
    """El Salvador SIGET utilities regulator lookup.

    Source: https://www.siget.gob.sv/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    provider_name: str = ""
    service_type: str = ""
    authorization_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
