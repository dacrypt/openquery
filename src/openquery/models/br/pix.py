"""Brazil PIX data model — PIX payment participants."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PixParticipant(BaseModel):
    """A PIX participant institution."""

    ispb: str = ""
    nome: str = ""
    cnpj: str = ""
    tipo_participacao: str = ""
    inicio_operacao: str = ""


class BrPixResult(BaseModel):
    """Brazil PIX participants lookup result.

    Source: https://brasilapi.com.br/api/pix/v1/participants
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    participantes: list[PixParticipant] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
