"""OSIPTEL data model — Peru telecom operators registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OsiptelResult(BaseModel):
    """Telecom operator data from Peru's OSIPTEL.

    Source: https://www.osiptel.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    operator_name: str = ""
    service_type: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
