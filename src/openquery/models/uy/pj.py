"""Uruguay Poder Judicial data model — case lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UyPjResult(BaseModel):
    """Uruguay Poder Judicial case lookup result.

    Source: https://expedientes.poderjudicial.gub.uy/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    sui: str = ""
    case_status: str = ""
    last_action: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
