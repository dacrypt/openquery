"""Brazil DataJud data model — CNJ judicial process lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MovimentoProcessual(BaseModel):
    """A judicial process movement."""

    data: str = ""
    nome: str = ""
    complemento: str = ""


class BrDatajudResult(BaseModel):
    """Brazil DataJud judicial process lookup result.

    Source: https://api-publica.datajud.cnj.jus.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    numero_processo: str = ""
    classe: str = ""
    sistema: str = ""
    orgao_julgador: str = ""
    tribunal: str = ""
    data_ajuizamento: str = ""
    assuntos: list[str] = Field(default_factory=list)
    movimentos: list[MovimentoProcessual] = Field(default_factory=list)
    total_movimentos: int = 0
    total_resultados: int = 0
    audit: Any | None = Field(default=None, exclude=True)
