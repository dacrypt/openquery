"""CNV data model — Argentina securities regulator."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CnvResult(BaseModel):
    """Registered entity data from Argentina's CNV.

    Source: https://www.cnv.gov.ar/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    registration_status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
