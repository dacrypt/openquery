"""El Salvador company registry data model — CNR."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SvEmpresaResult(BaseModel):
    """El Salvador company registry (CNR) lookup result.

    Source: https://www.e.cnr.gob.sv/ServiciosOL/portada/rco.htm
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_type: str = ""
    status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
