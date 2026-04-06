"""Paraguay MITIC open data portal source.

Queries Paraguay's MITIC open data portal (datos.gov.py CKAN API).
REST API, no auth, no CAPTCHA.

API: https://www.datos.gov.py/api/3/action/
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.mitic import PyMiticDataset, PyMiticResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MITIC_API_URL = "https://www.datos.gov.py/api/3/action"


@register
class PyMiticSource(BaseSource):
    """Search Paraguay MITIC open data portal (datos.gov.py)."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.mitic",
            display_name="MITIC — Datos Abiertos (PY)",
            description="Paraguay MITIC government open data portal: search datasets by query term",
            country="PY",
            url="https://www.datos.gov.py/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        q = input.extra.get("query", "") or input.document_number or ""
        if not q.strip():
            raise SourceError("py.mitic", "Query term is required")
        return self._search(q.strip())

    def _search(self, q: str) -> PyMiticResult:
        from datetime import datetime

        try:
            logger.info("Searching datos.gov.py (MITIC): %s", q)
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(
                    f"{MITIC_API_URL}/package_search",
                    params={"q": q, "rows": "10"},
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("result", {}).get("results", [])
            total = data.get("result", {}).get("count", 0)

            datasets = []
            for r in results:
                org = r.get("organization", {})
                datasets.append(
                    PyMiticDataset(
                        id=r.get("id", ""),
                        title=r.get("title", ""),
                        name=r.get("name", ""),
                        notes=(r.get("notes", "") or "")[:200],
                        organization=org.get("title", "") if isinstance(org, dict) else "",
                        url=f"https://www.datos.gov.py/dataset/{r.get('name', '')}",
                    )
                )

            return PyMiticResult(
                queried_at=datetime.now(),
                query=q,
                total_results=total,
                datasets=datasets,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("py.mitic", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("py.mitic", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("py.mitic", f"Query failed: {e}") from e
