"""DT employer lookup data model — Chile."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DtResult(BaseModel):
    """Dirección del Trabajo employer compliance lookup.

    Source: https://www.dt.gob.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    employer_name: str = ""
    compliance_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
