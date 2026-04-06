"""El Salvador Hacienda DUI/NIT data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SvHaciendaResult(BaseModel):
    """El Salvador Hacienda DUI/NIT registration lookup result.

    Source: https://portaldgii.mh.gob.sv/ssc/serviciosinclave/consulta/duinit/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dui: str = ""
    nit: str = ""
    taxpayer_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
