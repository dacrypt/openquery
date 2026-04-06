"""Panama ATTT data model — traffic/plate lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AtttPlacaResult(BaseModel):
    """Panama ATTT traffic and plate lookup result.

    Source: https://transito.gob.pa/servicios-en-linea/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    plate: str = ""
    fines_count: int = 0
    total_fines: str = ""
    plate_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
