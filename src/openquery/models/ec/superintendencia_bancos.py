"""Ecuador Superintendencia de Bancos entity data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EcSuperintendenciaBancosResult(BaseModel):
    """Ecuador Superintendencia de Bancos supervised entity lookup.

    Source: https://www.superbancos.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ruc: str = ""
    entity_name: str = ""
    entity_type: str = ""
    financial_data: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
