"""Peru Migraciones data model — immigration status lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MigracionesResult(BaseModel):
    """Peru immigration status lookup result.

    Source: https://www.migraciones.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    document_number: str = ""
    immigration_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
