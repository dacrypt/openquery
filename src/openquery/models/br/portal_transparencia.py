"""Brazil Portal da Transparência data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TransparenciaRecord(BaseModel):
    """A single record from the Portal da Transparência."""

    nome: str = ""
    cpf_cnpj: str = ""
    orgao: str = ""
    cargo: str = ""
    valor: str = ""
    details: str = ""


class BrPortalTransparenciaResult(BaseModel):
    """Brazil Portal da Transparência result.

    Source: https://api.portaldatransparencia.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    search_type: str = ""
    results_count: int = 0
    records: list[TransparenciaRecord] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
