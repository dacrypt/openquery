"""Paraguay datos.gov.py source — open data catalog.

Queries Paraguay's open data portal (CKAN API).
Free REST API, no auth, no CAPTCHA.

API: https://www.datos.gov.py/api/3/action/
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

API_URL = "https://www.datos.gov.py/api/3/action"


@register
class PyDatosSource(BaseSource):
    """Search Paraguay open data catalog (datos.gov.py)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.datos",
            display_name="Datos Abiertos PY — Portal de Datos",
            description="Paraguay open data catalog search (datos.gov.py CKAN API)",
            country="PY",
            url="https://www.datos.gov.py/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        q = input.extra.get("q", "") or input.document_number or "tipo cambio"
        return self._search(q.strip())

    def _search(self, q: str) -> CkanSearchResult:
        try:
            logger.info("Searching datos.gov.py: %s", q)
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(f"{API_URL}/package_search", params={"q": q, "rows": "10"})
                resp.raise_for_status()
                data = resp.json()

            results = data.get("result", {}).get("results", [])
            total = data.get("result", {}).get("count", 0)

            datasets = []
            for r in results:
                org = r.get("organization", {})
                datasets.append(CkanDataset(
                    id=r.get("id", ""),
                    title=r.get("title", ""),
                    name=r.get("name", ""),
                    notes=(r.get("notes", "") or "")[:200],
                    organization=org.get("title", "") if isinstance(org, dict) else "",
                    num_resources=r.get("num_resources", 0),
                    url=f"https://www.datos.gov.py/dataset/{r.get('name', '')}",
                ))

            return CkanSearchResult(
                queried_at=datetime.now(),
                query=q,
                portal="datos.gov.py",
                total=total,
                datasets=datasets,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("py.datos", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("py.datos", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("py.datos", f"Query failed: {e}") from e
