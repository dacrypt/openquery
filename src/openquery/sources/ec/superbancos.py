"""Ecuador Superbancos source — supervised financial entities.

Queries Superintendencia de Bancos portal for supervised banks and insurance entities.
Browser-based.

Source: https://www.superbancos.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.superbancos import SuperbancosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERBANCOS_URL = "https://www.superbancos.gob.ec/bancos/index.php/entidades-supervisadas"


@register
class SuperbancosSource(BaseSource):
    """Query Ecuador Superintendencia de Bancos for supervised entity status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.superbancos",
            display_name="Superbancos — Entidades Supervisadas (Ecuador)",
            description="Ecuador Superintendencia de Bancos supervised entities: banks and insurance",  # noqa: E501
            country="EC",
            url=SUPERBANCOS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError(
                "ec.superbancos",
                "Entity name is required (pass via extra.search_term or document_number)",
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SuperbancosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.superbancos", "search_term", search_term)

        with browser.page(SUPERBANCOS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="entidad" i], input[id*="entidad" i], '
                    'input[name*="search" i], input[id*="search" i], '
                    'input[placeholder*="entidad" i], input[placeholder*="buscar" i], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ec.superbancos", "Could not find entity search input field")
                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.superbancos", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SuperbancosResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SuperbancosResult(queried_at=datetime.now(), search_term=search_term)
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

            # Entity name
            if any(k in lower for k in ("entidad", "nombre", "institución", "institucion")):
                if ":" in stripped and not result.entity_name:
                    result.entity_name = stripped.split(":", 1)[1].strip()

            # Entity type
            if any(k in lower for k in ("tipo", "categoría", "categoria", "sector")):
                if ":" in stripped and not result.entity_type:
                    result.entity_type = stripped.split(":", 1)[1].strip()

            # Supervision status
            if any(  # noqa: E501
                k in lower
                for k in ("estado", "situación", "situacion", "supervisión", "supervision")
            ):
                if ":" in stripped and not result.supervision_status:
                    result.supervision_status = stripped.split(":", 1)[1].strip()

        if not result.entity_name:
            result.entity_name = search_term

        result.details = details
        return result
