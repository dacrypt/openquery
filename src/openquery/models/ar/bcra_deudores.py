"""BCRA Central de Deudores data model — Argentine credit report."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BcraDebt(BaseModel):
    """A single debt record from the BCRA central debtors registry."""

    entity: str = ""
    situation: int = 0
    amount: float = 0.0
    period: str = ""


class BcraDeudoresResult(BaseModel):
    """Credit report from Argentina's BCRA Central de Deudores.

    Source: https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas/{identificacion}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    identificacion: str = ""
    denominacion: str = ""
    total_debts: int = 0
    debts: list[BcraDebt] = Field(default_factory=list)
    periods_checked: int = 0
    worst_situation: int = 0
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
