"""DIGEMID data model — Peruvian drug registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DigemidResult(BaseModel):
    """DIGEMID (Direccion General de Medicamentos) drug registry (Peru).

    Source: https://www.digemid.minsa.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    product_name: str = ""
    registration_number: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
