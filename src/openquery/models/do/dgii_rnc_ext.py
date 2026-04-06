"""DGII RNC extended data model — Dominican Republic company registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DgiiRncExtResult(BaseModel):
    """Dominican Republic DGII RNC extended company info lookup.

    Source: https://dgii.gov.do/app/WebApps/ConsultasWeb/consultas/rnc.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rnc: str = ""
    company_name: str = ""
    commercial_name: str = ""
    status: str = ""
    economic_activity: str = ""
    address: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
