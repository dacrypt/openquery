"""SCVS data model — Ecuador Superintendencia de Compañías company registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScvsResult(BaseModel):
    """Company data from Ecuador's Superintendencia de Compañías, Valores y Seguros.

    Source: https://appscvsmovil.supercias.gob.ec/portalInformacion/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    ruc: str = ""
    status: str = ""
    legal_representative: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
