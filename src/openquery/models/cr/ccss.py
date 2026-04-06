"""Costa Rica CCSS social security model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CcssResult(BaseModel):
    """CCSS social security affiliation result for Costa Rica.

    Source: https://www.ccss.sa.cr/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    affiliation_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
