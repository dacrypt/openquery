"""Argentina IGJ data model — Inspección General de Justicia company registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IgjResult(BaseModel):
    """Company registration info from Argentina's IGJ (Inspección General de Justicia).

    Source: https://www2.jus.gov.ar/igj-vistas/Busqueda.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    correlative_number: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
