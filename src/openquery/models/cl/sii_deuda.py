"""SII Deuda data model — SII tax situation of third parties (Chile)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SiiDeudaResult(BaseModel):
    """Tax situation from Chile's SII (Servicio de Impuestos Internos) for third parties.

    Source: https://www.sii.cl/como_se_hace_para/situacion_trib_terceros.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    tax_status: str = ""
    has_debt: bool | None = None
    debt_indicators: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
