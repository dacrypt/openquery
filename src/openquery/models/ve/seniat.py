"""SENIAT data model — Venezuela RIF tax registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SeniatResult(BaseModel):
    """Venezuela SENIAT RIF tax registry lookup.

    Source: http://contribuyente.seniat.gob.ve/BuscaRif/BuscaRif.jsp
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rif: str = ""
    taxpayer_name: str = ""
    tax_status: str = ""
    taxpayer_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
