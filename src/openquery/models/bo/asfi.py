"""Bolivia ASFI supervised financial entities data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AsfiResult(BaseModel):
    """Bolivia ASFI supervised financial entity lookup result.

    Source: https://www.asfi.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    license_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
