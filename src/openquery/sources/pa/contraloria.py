"""Panama Contraloria source — government accountability news/reports.

Queries the Contraloría General de la República de Panamá via WordPress API.
Free REST API, no auth, no CAPTCHA.

API: https://www.contraloria.gob.pa/wp-json/wp/v2/posts
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.contraloria import ContraloriaPost, PaContraloriaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.contraloria.gob.pa/wp-json/wp/v2/posts"


@register
class PaContraloriaSource(BaseSource):
    """Query Panama Contraloria news and reports."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.contraloria",
            display_name="Contraloría — Noticias y Reportes",
            description="Panama Contraloría General news and accountability reports (WordPress API)",  # noqa: E501
            country="PA",
            url="https://www.contraloria.gob.pa/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search = input.extra.get("q", "") or input.document_number
        return self._query(search.strip() if search else "")

    def _query(self, search: str) -> PaContraloriaResult:
        try:
            params = {"per_page": "10"}
            if search:
                params["search"] = search

            logger.info("Querying Panama Contraloria: %s", search or "(latest)")
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            posts = []
            for p in data:
                title = (
                    p.get("title", {}).get("rendered", "")
                    if isinstance(p.get("title"), dict)
                    else str(p.get("title", ""))
                )
                excerpt = (
                    p.get("excerpt", {}).get("rendered", "")
                    if isinstance(p.get("excerpt"), dict)
                    else ""
                )
                excerpt_clean = re.sub(r"<[^>]+>", "", excerpt).strip()[:200]

                posts.append(
                    ContraloriaPost(
                        id=p.get("id", 0),
                        titulo=re.sub(r"<[^>]+>", "", title).strip(),
                        fecha=p.get("date", ""),
                        extracto=excerpt_clean,
                        url=p.get("link", ""),
                    )
                )

            return PaContraloriaResult(
                queried_at=datetime.now(),
                query=search,
                total=len(posts),
                posts=posts,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "pa.contraloria", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("pa.contraloria", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("pa.contraloria", f"Query failed: {e}") from e
