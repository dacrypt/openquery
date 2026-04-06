"""SSN Seguro data model — Argentine mandatory vehicle insurance check (SSN)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SsnSeguroResult(BaseModel):
    """Mandatory vehicle insurance result from Argentina's SSN.

    Source: https://seguro.ssn.gob.ar/
    """

    placa: str = ""
    has_insurance: bool = False
    insurer: str = ""
    policy_valid: bool = False
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
