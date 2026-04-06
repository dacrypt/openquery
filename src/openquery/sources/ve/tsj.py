"""TSJ source — Venezuela Supreme Court case lookup.

Queries the TSJ (Tribunal Supremo de Justicia) public consultation page
for court cases by case number or party name.

Flow:
1. Navigate to TSJ consultation page
2. Enter case number or party name
3. Submit search
4. Parse case status, chamber, and ruling

Source: https://www.tsj.gob.ve/en/consulta
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.tsj import TsjResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TSJ_URL = "https://www.tsj.gob.ve/en/consulta"


@register
class TsjSource(BaseSource):
    """Query Venezuela TSJ Supreme Court cases."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.tsj",
            display_name="TSJ — Consulta de Expedientes",
            description=("Venezuela Supreme Court case lookup: case status, chamber, and rulings"),
            country="VE",
            url=TSJ_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        case_number = input.extra.get("case_number", "")
        party_name = input.extra.get("party_name", "")
        search_term = case_number or party_name or input.document_number.strip()
        if not search_term:
            raise SourceError(
                "ve.tsj",
                "Search term is required (use extra.case_number, extra.party_name, or document_number)",  # noqa: E501
            )
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> TsjResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ve.tsj", "custom", search_term)

        with browser.page(TSJ_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                # Locate search input
                search_input = page.query_selector(
                    'input[name*="expediente"], input[name*="numero"], '
                    'input[name*="search"], input[name*="buscar"], '
                    'input[id*="expediente"], input[id*="search"], '
                    'input[type="text"], input[type="search"]'
                )
                if not search_input:
                    raise SourceError("ve.tsj", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying TSJ for: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar"), '
                    'input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.tsj", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> TsjResult:
        """Parse TSJ result page for case information."""
        from datetime import datetime

        body_text = page.inner_text("body")
        details: dict[str, str] = {}

        case_number = ""
        chamber = ""
        status = ""
        ruling = ""

        # Parse key:value lines
        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_clean = key.strip()
            val_clean = val.strip()
            if not val_clean:
                continue

            details[key_clean] = val_clean
            key_lower = key_clean.lower()

            if any(k in key_lower for k in ("expediente", "numero", "case")):
                if not case_number:
                    case_number = val_clean
            elif any(k in key_lower for k in ("sala", "tribunal", "chamber")):
                if not chamber:
                    chamber = val_clean
            elif any(k in key_lower for k in ("estado", "status", "estatus")):
                if not status:
                    status = val_clean
            elif any(
                k in key_lower for k in ("decisión", "decision", "fallo", "ruling", "sentencia")
            ):  # noqa: E501
                if not ruling:
                    ruling = val_clean

        # Fallback: regex patterns
        if not case_number:
            m = re.search(
                r"(?:Expediente|N[úu]mero|Case)[:\s]+([^\n]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                case_number = m.group(1).strip()

        if not chamber:
            m = re.search(
                r"(?:Sala|Tribunal|Chamber)[:\s]+([^\n]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                chamber = m.group(1).strip()

        if not status:
            m = re.search(
                r"(?:Estado|Estatus|Status)[:\s]+([^\n]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                status = m.group(1).strip()

        if not ruling:
            m = re.search(
                r"(?:Decisi[oó]n|Fallo|Ruling|Sentencia)[:\s]+([^\n]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                ruling = m.group(1).strip()

        return TsjResult(
            queried_at=datetime.now(),
            search_term=search_term,
            case_number=case_number,
            chamber=chamber,
            status=status,
            ruling=ruling,
            details=details,
        )
