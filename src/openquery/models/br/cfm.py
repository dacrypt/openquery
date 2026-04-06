"""CFM data model — Brazil doctor registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CfmResult(BaseModel):
    """CFM (Conselho Federal de Medicina) doctor registry result.

    Source: https://portal.cfm.org.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    crm_number: str = ""
    nome: str = ""
    specialty: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
