"""Dominican Republic INTRANT data model — driver license status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DoIntrantResult(BaseModel):
    """Dominican Republic INTRANT driver license status result.

    Source: https://www.intrant.gob.do/categoria/servicios/consulta-en-linea-estatus-de-licencias-de-conducir
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    license_status: str = ""
    expiration: str = ""
    fines_count: int = 0
    total_fines: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
