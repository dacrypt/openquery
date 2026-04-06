"""CREA data model — Brazil engineer registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreaResult(BaseModel):
    """CREA (Conselho Regional de Engenharia e Agronomia) engineer registry result.

    Source: https://www.crea-sp.org.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    crea_number: str = ""
    nome: str = ""
    specialty: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
