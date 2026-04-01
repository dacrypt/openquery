"""Contraloría General de la República data model — Colombian fiscal records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContraloriaResult(BaseModel):
    """Fiscal responsibility records from Colombia's Contraloría General.

    Source: https://www.contraloria.gov.co/web/guest/persona-natural
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    tiene_antecedentes_fiscales: bool = False
    mensaje: str = ""
    registros: list[dict] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
