"""Dominican Republic ONAPI data model — trademark search."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DoOnapiResult(BaseModel):
    """Dominican Republic ONAPI trademark search result.

    Source: https://www.onapi.gov.do/index.php/busqueda-de-signos-nombres-y-marcas
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    trademark_name: str = ""
    owner: str = ""
    status: str = ""
    registration_date: str = ""
    classes: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
