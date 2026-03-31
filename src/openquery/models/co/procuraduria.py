"""Procuraduria data model — Colombian disciplinary records."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProcuraduriaResult(BaseModel):
    """Disciplinary records from Colombia's Procuraduria General de la Nacion.

    Source: https://apps.procuraduria.gov.co/webcert/inicio.aspx?tpo=2
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    tipo_documento: str = ""
    tiene_antecedentes: bool = False
    mensaje: str = ""  # e.g., "No tiene antecedentes" or description of records
    certificado_url: str = ""  # URL to the PDF certificate if generated
    detalles: list[dict] = Field(default_factory=list)  # Parsed sanction details
