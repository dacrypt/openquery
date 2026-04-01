"""Licencias de Salud source — Colombian health service providers registry.

Queries the REPS (Registro Especial de Prestadores de Servicios de Salud)
via the datos.gov.co Socrata API. No browser or CAPTCHA required.

API: https://www.datos.gov.co/resource/g3r7-iqgd.json
Page: https://www.datos.gov.co/Salud-y-Protecci-n-Social/Prestadores-de-Servicios-de-Salud/g3r7-iqgd
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.licencias_salud import LicenciaSalud, LicenciasSaludResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/g3r7-iqgd.json"
PAGE_URL = (
    "https://www.datos.gov.co/Salud-y-Protecci-n-Social/"
    "Prestadores-de-Servicios-de-Salud/g3r7-iqgd"
)


@register
class LicenciasSaludSource(BaseSource):
    """Query Colombian health service providers registry (REPS) from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.licencias_salud",
            display_name="REPS — Prestadores de Servicios de Salud",
            description="Colombian health service providers registry (REPS) from datos.gov.co",
            country="CO",
            url=PAGE_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query health service providers by NIT or name."""
        if input.document_type not in (DocumentType.NIT, DocumentType.CUSTOM):
            raise SourceError(
                "co.licencias_salud",
                f"Unsupported input type: {input.document_type}",
            )

        nit = ""
        name = ""

        if input.document_type == DocumentType.NIT:
            nit = input.document_number.strip()
        else:
            name = input.extra.get("name", "").strip()

        if not nit and not name:
            raise SourceError(
                "co.licencias_salud",
                "Must provide a NIT or extra['name'] for search",
            )

        try:
            conditions = []
            if nit:
                conditions.append(f"numero_de_sede='{nit}' OR nits_nit='{nit}'")
            if name:
                prefix = name[:10].upper()
                conditions.append(
                    f"starts_with(upper(razon_social), '{prefix}')"
                )

            where_clause = " AND ".join(conditions)
            params: dict[str, str] = {"$where": where_clause, "$limit": "500"}

            logger.info("Querying REPS: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d REPS records", len(data))

            prestadores = []
            for row in data:
                prestadores.append(LicenciaSalud(
                    prestador=row.get("codigo_habilitacion", ""),
                    nit=row.get("nits_nit", ""),
                    nombre=row.get("razon_social", ""),
                    clase=row.get("clpr_nombre", ""),
                    naturaleza=row.get("clase_persona", ""),
                    departamento=row.get("depa_nombre", ""),
                    municipio=row.get("muni_nombre", ""),
                    direccion=row.get("direccion", ""),
                    telefono=row.get("telefono", ""),
                    estado=row.get("habilitado", ""),
                    nivel=row.get("nivel", ""),
                ))

            return LicenciasSaludResult(
                query=nit or name,
                total=len(prestadores),
                prestadores=prestadores,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("co.licencias_salud", msg) from e
        except httpx.RequestError as e:
            raise SourceError("co.licencias_salud", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.licencias_salud", f"Query failed: {e}") from e
