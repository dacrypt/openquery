"""SAT Lima data model — Peru SAT Lima vehicle taxes and papeletas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SatLimaResult(BaseModel):
    """Vehicle tax and papeleta record from Peru's SAT Lima.

    Source: https://www.sat.gob.pe/WebSiteV9/TributosMultas/Papeletas/ConsultasPapeletas
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    total_papeletas: int = 0
    total_amount: str = ""
    tax_status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
