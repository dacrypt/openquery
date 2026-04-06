"""Panama Registro Publico source — company registry.

Queries Panama's Registro Publico portal for company information.
Browser-based, public access.

Portal: https://www.rp.gob.pa/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.registro_publico import RegistroPublicoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PORTAL_URL = "https://www.rp.gob.pa/"


@register
class RegistroPublicoSource(BaseSource):
    """Query Panama Registro Publico for company registry information."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.registro_publico",
            display_name="Registro Público — Consulta de Sociedades",
            description=("Panama company registry lookup via Registro Público (rp.gob.pa)"),
            country="PA",
            url=PORTAL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("company_name", "")
            or input.extra.get("folio", "")
            or input.document_number.strip()
        )
        if not search_term:
            raise SourceError("pa.registro_publico", "Company name or folio number is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> RegistroPublicoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pa.registro_publico", "search", search_term)

        with browser.page(PORTAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Find search input
                search_input = page.query_selector(
                    'input[type="text"][id*="nombre"], '
                    'input[type="text"][name*="nombre"], '
                    'input[type="text"][id*="folio"], '
                    'input[type="text"][name*="folio"], '
                    'input[type="text"][placeholder*="ombre"], '
                    'input[type="text"][placeholder*="olio"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pa.registro_publico", "Could not find search input field")

                search_input.fill(search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button[class*="btn-primary"], button'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pa.registro_publico", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_term: str) -> RegistroPublicoResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()

        company_name = ""
        folio = ""
        registration_status = ""
        directors: list[str] = []
        details: dict[str, str] = {}

        if any(phrase in body_lower for phrase in ("no se encontr", "no registra", "sin result")):
            return RegistroPublicoResult(
                queried_at=datetime.now(),
                search_term=search_term,
            )

        # Parse key-value lines
        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_clean = key.strip().lower()
            val_clean = val.strip()

            if not val_clean:
                continue

            details[key.strip()] = val_clean

            if any(k in key_clean for k in ("nombre", "sociedad", "empresa", "company")):
                company_name = val_clean
            elif "folio" in key_clean:
                folio = val_clean
            elif any(k in key_clean for k in ("estado", "status")):
                registration_status = val_clean
            elif any(k in key_clean for k in ("director", "representante", "dignatario")):
                directors.append(val_clean)

        # Try to extract directors from table
        if not directors:
            try:
                rows = page.query_selector_all("table tr")  # type: ignore[union-attr]
                for row in rows[1:]:
                    cells = row.query_selector_all("td")
                    cell_texts = [c.inner_text().strip() for c in cells]
                    if cell_texts and any(
                        kw in " ".join(cell_texts).lower()
                        for kw in ("director", "representante", "presidente", "secretario")
                    ):
                        directors.append(" | ".join(t for t in cell_texts if t))
            except Exception:
                pass

        return RegistroPublicoResult(
            queried_at=datetime.now(),
            search_term=search_term,
            company_name=company_name,
            folio=folio,
            registration_status=registration_status,
            directors=directors,
            details=details,
        )
