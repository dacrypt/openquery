"""Paraguay DNCP government procurement model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PyDncpContract(BaseModel):
    """A single DNCP procurement contract entry."""

    convocatoria: str = ""
    monto: str = ""
    estado: str = ""
    fecha: str = ""


class PyDncpResult(BaseModel):
    """Data from Paraguay DNCP government procurement portal.

    Source: https://www.contrataciones.gov.py/
    """

    search_term: str = ""
    total_contracts: int = 0
    contracts: list[PyDncpContract] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
