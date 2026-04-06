"""Argentina COPREC data model — consumer mediation records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CoprecResult(BaseModel):
    """COPREC consumer mediation records lookup result.

    Source: https://www.argentina.gob.ar/produccion/defensadelconsumidor/formulario
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    total_records: int = 0
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
