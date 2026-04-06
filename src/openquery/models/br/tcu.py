"""Brazil TCU data model — government audit/sanctions (licitantes inidôneos)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrTcuResult(BaseModel):
    """Brazil TCU inidoneidade (government sanctions) result.

    Source: https://portal.tcu.gov.br/licitantes-inidoneos/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    cnpj: str = ""
    sanction_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
