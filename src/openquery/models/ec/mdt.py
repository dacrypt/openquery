"""MDT data model — Ecuador Ministerio del Trabajo labor consultation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MdtResult(BaseModel):
    """Labor registration data from Ecuador's Ministerio del Trabajo.

    Source: https://www.trabajo.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    employer_name: str = ""
    labor_status: str = ""
    contract_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
