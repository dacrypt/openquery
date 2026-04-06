"""Bolivia TSJ court processes data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TsjProcess(BaseModel):
    """A single court process record from TSJ."""

    case_number: str = ""
    court: str = ""
    status: str = ""
    parties: str = ""
    date: str = ""


class TsjProcesosResult(BaseModel):
    """Bolivia TSJ court case search result.

    Source: https://tsj.bo/servicios-judiciales/plataforma-servicios/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    total: int = 0
    processes: list[TsjProcess] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
