"""Registro Civil data model — Chilean document validity check."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegistroCivilResult(BaseModel):
    """Document validity status from Chile's Registro Civil (SIDIV portal).

    Source: https://portal.sidiv.registrocivil.cl/usuarios-portal/pages/DocumentRequestStatus.xhtml
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    run: str = ""
    serial_number: str = ""
    document_status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
