"""CMF Fiscalizados data model — CMF supervised financial entities (Chile)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CmfFiscalizadosResult(BaseModel):
    """Supervised entity information from Chile's CMF (Comision para el Mercado Financiero).

    Source: https://www.cmfchile.cl/portal/principal/613/w3-propertyvalue-43336.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    rut: str = ""
    entity_type: str = ""
    authorization_status: str = ""
    address: str = ""
    branches: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
