"""Poder Judicial SUMAC case lookup model — Puerto Rico."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TribunalesResult(BaseModel):
    """Data from Puerto Rico's Poder Judicial SUMAC case lookup.

    Source: https://poderjudicial.pr/consulta-de-casos/
    """

    search_term: str = ""
    case_number: str = ""
    court: str = ""
    status: str = ""
    parties: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
