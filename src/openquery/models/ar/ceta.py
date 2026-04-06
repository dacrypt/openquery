"""CETA data model — DNRPA transfer certificate status."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CetaResult(BaseModel):
    """CETA (transfer certificate) status from Argentina's DNRPA.

    Source: https://www.dnrpa.gov.ar/portal_dnrpa/fabr_import2.php?EstadoCertificado=true
    """

    placa: str = ""
    ceta_status: str = ""
    issuance_date: str = ""
    expiration_date: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
