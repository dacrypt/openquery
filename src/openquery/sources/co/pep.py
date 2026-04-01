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

# Función Pública — FDCI PEP consultation (GET form, no CAPTCHA on individual search)
PEP_API_URL = "https://www.funcionpublica.gov.co/fdci/consultaCiudadana/consultaPEP"
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
            description="Colombian Politically Exposed Persons screening (SIGEP public officials directory)",
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
            params: dict[str, str] = {}

            if documento:
                params["numeroDocumento"] = documento
                logger.info("Searching PEP by document: %s", documento)
            elif nombre:
                parts = nombre.split(maxsplit=1)
                params["primerNombre"] = parts[0]
                if len(parts) > 1:
                    params["primerApellido"] = parts[1]
                logger.info("Searching PEP by name: %s", nombre)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(PEP_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            registros = []
            for entry in data:
                nombre_completo = " ".join(filter(None, [
                    entry.get("primer_nombre", ""),
                    entry.get("segundo_nombre", ""),
                    entry.get("primer_apellido", ""),
                    entry.get("segundo_apellido", ""),
                ]))
                registros.append(PepEntry(
                    nombre=nombre_completo.strip(),
                    cargo=entry.get("nombre_del_cargo", ""),
                    entidad=entry.get("nombre_entidad", ""),
                    fecha_vinculacion=entry.get("fecha_de_vinculaci_n", ""),
                    estado=entry.get("tipo_de_vinculaci_n", ""),
                ))

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
