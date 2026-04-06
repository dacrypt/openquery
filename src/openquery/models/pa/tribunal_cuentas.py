"""Panama Tribunal de Cuentas data model — audit findings lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TribunalCuentasResult(BaseModel):
    """Tribunal de Cuentas audit findings lookup result.

    Source: https://www.tribunaldecuentas.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    findings: list[dict[str, str]] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
