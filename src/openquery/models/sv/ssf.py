"""SSF banking supervisor data model — El Salvador."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SsfResult(BaseModel):
    """SSF (Superintendencia del Sistema Financiero) supervised entity lookup.

    Source: https://www.ssf.gob.sv/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
