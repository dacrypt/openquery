"""Brazil ANTT RNTRC data model — carrier registry lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnttRntrcResult(BaseModel):
    """Brazil ANTT RNTRC carrier registry lookup result.

    Source: https://consultapublica.antt.gov.br/Site/ConsultaRNTRC.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_type: str = ""  # cnpj, cpf, rntrc, plate
    search_value: str = ""
    rntrc_number: str = ""
    carrier_name: str = ""
    status: str = ""
    transport_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
