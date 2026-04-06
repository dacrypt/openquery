"""Brazil TSE candidate/politician data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrTseCandidatosResult(BaseModel):
    """Brazil TSE candidate/politician lookup result.

    Source: https://dadosabertos.tse.jus.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    candidate_name: str = ""
    cpf: str = ""
    party: str = ""
    position: str = ""
    election_year: str = ""
    declared_assets: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
