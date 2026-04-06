"""CFC accountant registry data model — Brazil."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CfcResult(BaseModel):
    """CFC (Conselho Federal de Contabilidade) accountant registry lookup.

    Source: https://www.cfc.org.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    crc_number: str = ""
    nome: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
