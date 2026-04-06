"""Costa Rica Ministerio de Hacienda tax declarant status data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrHaciendaResult(BaseModel):
    """Costa Rica Hacienda tax declarant status lookup result.

    Source: https://ticaconsultas.hacienda.go.cr/Tica/hrgdeclarantescedula.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    declarant_status: str = ""
    obligations: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
