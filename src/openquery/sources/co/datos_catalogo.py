"""Colombia datos.gov.co catalog source — open data catalog search.

Queries Colombia's Socrata open data catalog for datasets.
Free REST API, no auth, no CAPTCHA.

API: https://www.datos.gov.co/api/catalog/v1
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.datos_catalogo import DatosCatalogoEntry, DatosCatalogoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/api/catalog/v1"


@register
class DatosCatalogoSource(BaseSource):
    """Search Colombia datos.gov.co open data catalog."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.datos_catalogo",
            display_name="Datos Abiertos CO — Catálogo de Datos",
            description="Colombia open data catalog search (datos.gov.co Socrata API)",
            country="CO",
            url="https://www.datos.gov.co/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        q = input.extra.get("q", "") or input.document_number or "transporte"
        return self._search(q.strip())

    def _search(self, q: str) -> DatosCatalogoResult:
        try:
            params = {
                "domains": "www.datos.gov.co",
                "search_context": "www.datos.gov.co",
                "q": q,
                "limit": "10",
            }
            logger.info("Searching datos.gov.co catalog: %s", q)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            total = data.get("resultSetSize", len(results))

            datasets = []
            for r in results:
                res = r.get("resource", {})
                datasets.append(DatosCatalogoEntry(
                    nombre=res.get("name", ""),
                    descripcion=(res.get("description", "") or "")[:200],
                    entidad=r.get("classification", {}).get("domain_metadata", [{}])[0].get("value", "") if r.get("classification", {}).get("domain_metadata") else "",
                    categoria=r.get("classification", {}).get("categories", [""])[0] if r.get("classification", {}).get("categories") else "",
                    url=r.get("link", ""),
                    recurso_id=res.get("id", ""),
                ))

            return DatosCatalogoResult(
                queried_at=datetime.now(),
                query=q,
                total=total,
                datasets=datasets,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("co.datos_catalogo", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("co.datos_catalogo", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.datos_catalogo", f"Query failed: {e}") from e
