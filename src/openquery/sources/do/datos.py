"""Dominican Republic datos.gob.do source — open data catalog.

Queries the Dominican Republic's open data portal (CKAN API).
Free REST API, no auth, no CAPTCHA.

API: https://datos.gob.do/api/3/action/
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

API_URL = "https://datos.gob.do/api/3/action"


@register
class DoDatosSource(BaseSource):
    """Search Dominican Republic open data catalog (datos.gob.do)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.datos",
            display_name="Datos Abiertos RD — Portal de Datos",
            description="Dominican Republic open data catalog search (datos.gob.do CKAN API)",
            country="DO",
            url="https://datos.gob.do/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        q = input.extra.get("q", "") or input.document_number or "poblacion"
        return self._search(q.strip())

    def _search(self, q: str) -> CkanSearchResult:
        try:
            logger.info("Searching datos.gob.do: %s", q)
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
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
                        url=f"https://datos.gob.do/dataset/{r.get('name', '')}",
                    )
                )

            return CkanSearchResult(
                queried_at=datetime.now(),
                query=q,
                portal="datos.gob.do",
                total=total,
                datasets=datasets,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("do.datos", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("do.datos", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("do.datos", f"Query failed: {e}") from e
