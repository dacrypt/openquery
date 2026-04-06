"""Panama ATTT source — traffic/plate lookup.

Queries Panama's ATTT portal for traffic fines and plate status.
Browser-based, public access.

Portal: https://transito.gob.pa/servicios-en-linea/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.attt_placa import AtttPlacaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PORTAL_URL = "https://transito.gob.pa/servicios-en-linea/"


@register
class AtttPlacaSource(BaseSource):
    """Query Panama ATTT for traffic fines and plate status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.attt_placa",
            display_name="ATTT — Consulta de Multas y Placas",
            description=(
                "Panama traffic fines and plate status lookup via ATTT (transito.gob.pa)"
            ),
            country="PA",
            url=PORTAL_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("plate", "") or input.document_number.strip()
        if not search_value:
            raise SourceError("pa.attt_placa", "Plate number or cedula is required")
        return self._query(search_value, audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> AtttPlacaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pa.attt_placa", "plate", search_value)

        with browser.page(PORTAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Find plate/cedula input
                search_input = page.query_selector(
                    'input[type="text"][id*="placa"], '
                    'input[type="text"][name*="placa"], '
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"][placeholder*="laca"], '
                    'input[type="text"][placeholder*="edula"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pa.attt_placa", "Could not find search input field")

                search_input.fill(search_value)

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

                result = self._parse_result(page, search_value)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pa.attt_placa", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_value: str) -> AtttPlacaResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()

        plate = ""
        fines_count = 0
        total_fines = ""
        plate_status = ""
        details: dict[str, str] = {}

        not_found_phrases = ("no se encontr", "no registra", "sin result", "no existe")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return AtttPlacaResult(
                queried_at=datetime.now(),
                search_value=search_value,
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

            if "placa" in key_clean:
                plate = val_clean
            elif any(k in key_clean for k in ("estado", "status")):
                plate_status = val_clean
            elif any(k in key_clean for k in ("total", "monto", "amount")):
                total_fines = val_clean
            elif any(k in key_clean for k in ("cantidad", "multas", "infracciones", "count")):
                try:
                    fines_count = int("".join(filter(str.isdigit, val_clean)) or "0")
                except ValueError:
                    pass

        # Try to count fine rows from table
        if fines_count == 0:
            try:
                rows = page.query_selector_all("table tr")  # type: ignore[union-attr]
                data_rows = [r for r in rows[1:] if r.query_selector("td")]
                fines_count = len(data_rows)
            except Exception:
                pass

        # Use search_value as plate if not parsed
        if not plate:
            plate = search_value

        return AtttPlacaResult(
            queried_at=datetime.now(),
            search_value=search_value,
            plate=plate,
            fines_count=fines_count,
            total_fines=total_fines,
            plate_status=plate_status,
            details=details,
        )
