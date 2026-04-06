"""Guatemala RENAP data model — DPI identity status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtRenapResult(BaseModel):
    """Guatemala RENAP DPI processing status lookup result.

    Source: https://www.renap.gob.gt/estado-tramite-dpi
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dpi: str = ""
    nombre: str = ""
    status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
