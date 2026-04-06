"""IVSS data model — Venezuela social security."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IvssResult(BaseModel):
    """Venezuela social security enrollment lookup via IVSS.

    Source: http://www.ivss.gob.ve:28088/ConstanciaCotizacion/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    enrollment_status: str = ""
    contribution_status: str = ""
    employer: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
