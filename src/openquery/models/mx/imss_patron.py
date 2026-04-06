"""Mexico IMSS employer registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImssPatronResult(BaseModel):
    """IMSS employer registry lookup result.

    Source: https://serviciosdigitales.imss.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    registro_patronal: str = ""
    employer_name: str = ""
    status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
