"""Policia Nacional data model — Colombian judicial records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PoliciaResult(BaseModel):
    """Judicial background records from Colombia's Policia Nacional.

    Source: https://antecedentes.policia.gov.co:7005/WebJudicial/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    tiene_antecedentes: bool = False
    mensaje: str = ""  # "No tiene asuntos pendientes" or details
    detalles: list[dict] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)  # AuditRecord when audit=True
