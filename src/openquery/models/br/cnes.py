"""CNES data model — Brazilian health facility registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CnesResult(BaseModel):
    """CNES (Cadastro Nacional de Estabelecimentos de Saude) health facility registry (Brazil).

    Source: https://cnes.datasus.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    facility_name: str = ""
    cnes_code: str = ""
    facility_type: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
