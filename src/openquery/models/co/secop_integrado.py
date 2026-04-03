"""SECOP Integrado data model — Colombian unified procurement contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SecopContrato(BaseModel):
    """A contract from SECOP Integrado."""

    entidad: str = ""
    nit_entidad: str = ""
    proveedor: str = ""
    documento_proveedor: str = ""
    estado: str = ""
    modalidad: str = ""
    objeto: str = ""
    valor: str = ""
    departamento: str = ""
    municipio: str = ""


class SecopIntegradoResult(BaseModel):
    """SECOP Integrado unified procurement results.

    Source: https://www.datos.gov.co/resource/rpmr-utcd.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    contratos: list[SecopContrato] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
