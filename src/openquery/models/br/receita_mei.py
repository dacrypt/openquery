"""Receita Federal MEI microentrepreneur data model — Brazil."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReceitaMeiResult(BaseModel):
    """Receita Federal MEI (Microempreendedor Individual) status lookup.

    Source: https://www.gov.br/empresas-e-negocios/pt-br/empreendedor
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cnpj: str = ""
    nome: str = ""
    mei_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
