"""CFE electricity account data model — Mexico."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CfeResult(BaseModel):
    """CFE (Comisión Federal de Electricidad) account status lookup.

    Source: https://www.cfe.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    service_number: str = ""
    account_status: str = ""
    balance: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
