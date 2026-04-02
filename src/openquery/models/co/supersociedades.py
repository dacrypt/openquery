"""Supersociedades data model — Colombian insolvency proceedings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InsolvencyProceeding(BaseModel):
    """A single insolvency proceeding from Supersociedades."""

    tipo_proceso: str = ""
    estado: str = ""
    fecha_admision: str = ""
    juzgado: str = ""
    promotor: str = ""
    modalidad: str = ""


class SupersociedadesResult(BaseModel):
    """Supersociedades insolvency search results.

    Source: https://www.supersociedades.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    razon_social: str = ""
    nit: str = ""
    estado: str = ""
    procesos: list[InsolvencyProceeding] = Field(default_factory=list)
    total_procesos: int = 0
    tiene_proceso_insolvencia: bool = False
    audit: Any | None = Field(default=None, exclude=True)
