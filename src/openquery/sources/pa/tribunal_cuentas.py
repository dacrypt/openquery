"""Panama Tribunal de Cuentas source — audit findings lookup.

Queries Panama Tribunal de Cuentas portal for audit findings and
processes by entity name.
Browser-based, public access.

Source: https://www.tribunaldecuentas.gob.pa/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.tribunal_cuentas import TribunalCuentasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TRIBUNAL_CUENTAS_URL = "https://www.tribunaldecuentas.gob.pa/procesos"


@register
class TribunalCuentasSource(BaseSource):
    """Query Panama Tribunal de Cuentas for audit findings."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.tribunal_cuentas",
            display_name="Tribunal de Cuentas — Procesos y Hallazgos",
            description="Panama Tribunal de Cuentas audit findings and processes lookup by entity name",  # noqa: E501
            country="PA",
            url=TRIBUNAL_CUENTAS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("pa.tribunal_cuentas", "Entity name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> TribunalCuentasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pa.tribunal_cuentas", "search_term", search_term)

        with browser.page(TRIBUNAL_CUENTAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[placeholder*="entidad" i], input[placeholder*="buscar" i], '
                    'input[name*="search" i], input[id*="search" i], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError(
                        "pa.tribunal_cuentas", "Could not find search input field"
                    )

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar" i], button[id*="consultar" i]'
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
                raise SourceError("pa.tribunal_cuentas", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_term: str) -> TribunalCuentasResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()
        entity_name = ""
        findings: list[dict[str, str]] = []
        details: dict[str, str] = {}

        not_found_phrases = ("no se encontr", "sin resultados", "no registra", "no existe")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return TribunalCuentasResult(
                queried_at=datetime.now(),
                search_term=search_term,
            )

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key_clean = key.strip()
                val_clean = val.strip()
                if val_clean:
                    details[key_clean] = val_clean

                if any(k in lower for k in ("entidad", "institución", "nombre")):
                    if not entity_name and val_clean:
                        entity_name = val_clean

        # Extract findings from table rows
        try:
            rows = page.query_selector_all("table tr")  # type: ignore[union-attr]
            for row in rows[1:]:
                tds = row.query_selector_all("td")
                if tds and len(tds) >= 2:
                    finding: dict[str, str] = {}
                    for i, td in enumerate(tds):
                        text = td.inner_text().strip()
                        if text:
                            finding[f"col_{i}"] = text
                    if finding:
                        findings.append(finding)
        except Exception:
            pass

        return TribunalCuentasResult(
            queried_at=datetime.now(),
            search_term=search_term,
            entity_name=entity_name,
            findings=findings,
            details=details,
        )
