"""DGII NCF data model — Dominican Republic NCF invoice verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DoDgiiNcfResult(BaseModel):
    """Dominican Republic DGII NCF invoice validity result.

    Source: https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultaNCF2/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rnc: str = ""
    ncf: str = ""
    ncf_valid: bool = False
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
