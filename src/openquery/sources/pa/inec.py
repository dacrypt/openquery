"""Panama INEC source — national statistics.

Queries Panama's INEC (Instituto Nacional de Estadística y Censo) API.
Free REST API, no auth, no CAPTCHA.

API: https://www.inec.gob.pa/m_2/api/tipos
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.inec import InecCategoria, PaInecResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.inec.gob.pa/m_2/api/tipos"


@register
class PaInecSource(BaseSource):
    """Query Panamanian national statistics categories (INEC)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.inec",
            display_name="INEC — Estadísticas Nacionales",
            description="Panama national statistics categories (Instituto Nacional de Estadística y Censo)",
            country="PA",
            url="https://www.inec.gob.pa/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        return self._query()

    def _query(self) -> PaInecResult:
        try:
            logger.info("Querying Panama INEC statistics categories")
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL)
                resp.raise_for_status()
                data = resp.json()

            categorias = []
            items = data if isinstance(data, list) else data.get("data", data.get("tipos", []))
            for item in items:
                if isinstance(item, dict):
                    categorias.append(InecCategoria(
                        id=str(item.get("id", item.get("tipo_id", ""))),
                        nombre=item.get("nombre", item.get("tipo", "")),
                        descripcion=item.get("descripcion", ""),
                    ))

            return PaInecResult(
                queried_at=datetime.now(),
                query="categorias",
                total=len(categorias),
                categorias=categorias,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("pa.inec", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("pa.inec", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("pa.inec", f"Query failed: {e}") from e
