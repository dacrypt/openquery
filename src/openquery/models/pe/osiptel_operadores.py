"""OSIPTEL licensed operators data model — Peru."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OsiptelOperadoresResult(BaseModel):
    """OSIPTEL licensed telecom operators lookup.

    Source: https://www.osiptel.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    operator_name: str = ""
    service_type: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
