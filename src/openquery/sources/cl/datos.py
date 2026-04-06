"""Chile datos.gob.cl source — open data catalog.

Queries Chile's open data portal (CKAN API).
Free REST API, no auth, no CAPTCHA.

API: https://datos.gob.cl/api/3/action/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.common_ckan import CkanDataset, CkanSearchResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://datos.gob.cl/api/3/action"


@register
class ClDatosSource(BaseSource):
    """Search Chile open data catalog (datos.gob.cl)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.datos",
            display_name="Datos Abiertos CL — Portal de Datos",
            description="Chile open data catalog search (datos.gob.cl CKAN API, 10000+ datasets)",
            country="CL",
            url="https://datos.gob.cl/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        q = input.extra.get("q", "") or input.document_number or "salud"
        return self._search(q.strip())

    def _search(self, q: str) -> CkanSearchResult:
        try:
            logger.info("Searching datos.gob.cl: %s", q)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/package_search", params={"q": q, "rows": "10"})
                resp.raise_for_status()
                data = resp.json()

            results = data.get("result", {}).get("results", [])
            total = data.get("result", {}).get("count", 0)

            datasets = []
            for r in results:
                org = r.get("organization", {})
                datasets.append(
                    CkanDataset(
                        id=r.get("id", ""),
                        title=r.get("title", ""),
                        name=r.get("name", ""),
                        notes=(r.get("notes", "") or "")[:200],
                        organization=org.get("title", "") if isinstance(org, dict) else "",
                        num_resources=r.get("num_resources", 0),
                        url=f"https://datos.gob.cl/dataset/{r.get('name', '')}",
                    )
                )

            return CkanSearchResult(
                queried_at=datetime.now(),
                query=q,
                portal="datos.gob.cl",
                total=total,
                datasets=datasets,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("cl.datos", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("cl.datos", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("cl.datos", f"Query failed: {e}") from e
