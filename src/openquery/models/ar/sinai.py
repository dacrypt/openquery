"""SINAI data model — Argentine national traffic infractions (ANSV)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SinaiInfraction(BaseModel):
    """Single infraction record from SINAI."""

    date: str = ""
    description: str = ""
    amount: str = ""
    status: str = ""


class SinaiResult(BaseModel):
    """Traffic infractions result from Argentina's SINAI / ANSV.

    Source: https://consultainfracciones.seguridadvial.gob.ar/
    """

    placa: str = ""
    total_infractions: int = 0
    infractions: list[SinaiInfraction] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
