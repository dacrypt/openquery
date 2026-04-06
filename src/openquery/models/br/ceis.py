"""CEIS data model — Brazilian sanctioned companies registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CeisResult(BaseModel):
    """CEIS (Cadastro de Empresas Inidoneas e Suspensas) sanctioned companies (Brazil).

    Source: https://www.portaltransparencia.gov.br/sancoes/ceis
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    cnpj: str = ""
    sanction_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
