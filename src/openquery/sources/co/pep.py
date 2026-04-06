"""PEP source — Politically Exposed Persons screening for Colombia.

Queries Colombian PEP lists to check if a person holds or has held
prominent public functions.

Uses datos.gov.co Socrata API for the SIGEP (public employment) dataset.
No browser or CAPTCHA required — direct HTTP.

API: https://www.datos.gov.co/resource/cnjr-gkzr.json (SIGEP)
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.pep import PepEntry, PepResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# datos.gov.co Socrata API — SIGEP public officials dataset (reliable, no SSL issues)
PEP_API_URL = "https://www.datos.gov.co/resource/3qxn-uc22.json"
PEP_PAGE_URL = "https://www.funcionpublica.gov.co/fdci/consultaCiudadana/consultaPEP"


@register
class PepSource(BaseSource):
    """Screen persons against Colombian PEP (public officials) lists."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.pep",
            display_name="PEP — Personas Expuestas Políticamente",
            description="Colombian Politically Exposed Persons screening (SIGEP public officials directory)",  # noqa: E501
            country="CO",
            url=PEP_PAGE_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        doc_number = input.document_number.strip()
        name = input.extra.get("name", "").strip()

        if not doc_number and not name:
            raise SourceError("co.pep", "Provide a document number or name (extra.name) to search")

        return self._search(doc_number, name)

    def _search(self, documento: str, nombre: str = "") -> PepResult:
        try:
            params: dict[str, str] = {"$limit": "50"}

            if documento:
                params["$where"] = f"numero_documento='{documento}'"
                logger.info("Searching PEP by document: %s", documento)
            elif nombre:
                prefix = nombre[:10].upper()
                params["$where"] = f"starts_with(upper(nombre_pep), '{prefix}')"
                logger.info("Searching PEP by name: %s", nombre)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(PEP_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            registros = []
            for entry in data:
                registros.append(
                    PepEntry(
                        nombre=entry.get("nombre_pep", ""),
                        cargo=entry.get("denominacion_cargo", entry.get("nombre_del_cargo", "")),
                        entidad=entry.get("nombre_entidad", ""),
                        fecha_vinculacion=entry.get(
                            "fecha_vinculacion", entry.get("fecha_de_vinculaci_n", "")
                        ),
                        estado=entry.get(
                            "fecha_desvinculacion", entry.get("tipo_de_vinculaci_n", "")
                        ),
                    )
                )

            return PepResult(
                queried_at=datetime.now(),
                documento=documento,
                nombre_consultado=nombre,
                es_pep=len(registros) > 0,
                match_count=len(registros),
                registros=registros,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("co.pep", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("co.pep", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.pep", f"PEP search failed: {e}") from e
