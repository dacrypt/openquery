"""Peru Migraciones source — immigration status lookup.

Queries Peru Migraciones portal for immigration status by passport or CE number.
Browser-based.

Source: https://www.migraciones.gob.pe/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.migraciones import MigracionesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MIGRACIONES_URL = "https://www.migraciones.gob.pe/consultas/consulta_migrante.php"


@register
class MigracionesSource(BaseSource):
    """Query Peru Migraciones for immigration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.migraciones",
            display_name="Migraciones Perú — Consulta de Migrante",
            description="Peru immigration status lookup by passport or CE number (Migraciones)",
            country="PE",
            url=MIGRACIONES_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        doc = input.extra.get("document_number", "") or input.document_number
        if not doc:
            raise SourceError(
                "pe.migraciones",
                "Document number is required (passport or CE number)",
            )
        return self._query(doc.strip(), audit=input.audit)

    def _query(self, document_number: str, audit: bool = False) -> MigracionesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.migraciones", "document_number", document_number)

        with browser.page(MIGRACIONES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                doc_input = page.query_selector(
                    'input[name*="documento" i], input[name*="pasaporte" i], '
                    'input[id*="documento" i], input[placeholder*="documento" i], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("pe.migraciones", "Could not find document input field")

                doc_input.fill(document_number)
                logger.info("Filled document: %s", document_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, document_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.migraciones", f"Query failed: {e}") from e

    def _parse_result(self, page, document_number: str) -> MigracionesResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = MigracionesResult(queried_at=datetime.now(), document_number=document_number)
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

            # Immigration status
            if any(k in lower for k in ("estado", "situación", "situacion", "migratorio")):
                if ":" in stripped and not result.immigration_status:
                    result.immigration_status = stripped.split(":", 1)[1].strip()

        result.details = details
        return result
