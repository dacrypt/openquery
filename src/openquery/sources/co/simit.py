"""SIMIT source — Colombian traffic fines system.

Queries Colombia's SIMIT via Playwright headless browser.
The SIMIT website is an Angular SPA with no public REST API.

Flow:
1. Navigate to https://www.fcm.org.co/simit/#/estado-cuenta
2. Wait for form to load
3. Fill cedula/plate in the text input
4. Click "Realizar consulta"
5. Parse summary and optional historial table
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.simit import SimitResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SIMIT_URL = "https://www.fcm.org.co/simit/#/estado-cuenta"


@register
class SimitSource(BaseSource):
    """Query Colombia's SIMIT traffic fines system."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.simit",
            display_name="SIMIT — Multas de Tránsito",
            description="Colombian traffic fines and violations system (FCM)",
            country="CO",
            url=SIMIT_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query SIMIT for traffic fines."""
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PLATE):
            raise SourceError("co.simit", f"Unsupported input type: {input.document_type}")

        return self._query(input.document_number, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SimitResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.simit", "cedula/placa", search_term)

        with browser.page(SIMIT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for the Angular SPA to render
                logger.info("Waiting for search form...")
                input_locator = page.get_by_label("Número de identificación o placa del vehículo")
                input_locator.wait_for(state="visible", timeout=15000)

                # Fill search term
                input_locator.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Wait for anti-bot JS to enable the button
                page.wait_for_timeout(2000)

                # Click submit
                submit_locator = page.get_by_role("button", name="Realizar consulta")
                submit_locator.click()
                logger.info("Clicked submit button")

                # Wait for results
                page.wait_for_selector(
                    'strong, [class*="resumen"], [class*="result"], h3:has-text("No tienes")',
                    timeout=20000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                # Parse results
                result = self._parse_results(page, search_term)
                result.historial = self._parse_historial(page)

                # Generate audit evidence
                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.simit", f"Query failed: {e}") from e

    def _parse_results(self, page, search_term: str) -> SimitResult:
        """Parse the results summary from the page DOM."""
        data = SimitResult(queried_at=datetime.now(), cedula=search_term)

        # Check for "paz y salvo" (no fines)
        paz_salvo_img = page.query_selector('img[alt*="Paz y Salvo"], img[alt*="paz y salvo"]')
        no_fines_heading = page.query_selector('h3:has-text("No tienes comparendos ni multas")')

        if paz_salvo_img or no_fines_heading:
            data.paz_y_salvo = True
            logger.info("Paz y salvo — no fines found")

        body_text = page.inner_text("body")

        m = re.search(r"Comparendos:\s*(\d+)", body_text)
        if m:
            data.comparendos = int(m.group(1))

        m = re.search(r"Multas:\s*(\d+)", body_text)
        if m:
            data.multas = int(m.group(1))

        m = re.search(r"Acuerdos de pago:\s*(\d+)", body_text)
        if m:
            data.acuerdos_pago = int(m.group(1))

        m = re.search(r"Total:\s*\$\s*([\d.,]+)", body_text)
        if m:
            amount_str = m.group(1).replace(".", "").replace(",", ".")
            try:
                data.total_deuda = float(amount_str)
            except ValueError:
                data.total_deuda = 0.0

        if data.comparendos == 0 and data.multas == 0 and data.total_deuda == 0:
            data.paz_y_salvo = True

        logger.info(
            "SIMIT results — comparendos=%d, multas=%d, acuerdos=%d, total=$%.0f, paz_y_salvo=%s",
            data.comparendos,
            data.multas,
            data.acuerdos_pago,
            data.total_deuda,
            data.paz_y_salvo,
        )
        return data

    def _parse_historial(self, page) -> list[dict]:
        """Try to click 'Ver historial' and parse the historical records table."""
        historial = []
        try:
            historial_btn = page.query_selector('button:has-text("Ver historial")')
            if not historial_btn:
                logger.info("No historial button found")
                return historial

            btn_text = historial_btn.inner_text()
            logger.info("Found historial button: %s", btn_text)

            historial_btn.click()
            page.wait_for_timeout(2000)

            rows = page.query_selector_all("table tbody tr")
            if not rows:
                logger.info("No historial rows found")
                return historial

            for row in rows:
                cells = row.query_selector_all("td")
                if len(cells) >= 8:
                    record = {
                        "comparendo": (cells[0].inner_text() or "").strip(),
                        "secretaria": (cells[1].inner_text() or "").strip(),
                        "fecha_curso": (cells[2].inner_text() or "").strip(),
                        "numero_curso": (cells[3].inner_text() or "").strip(),
                        "ciudad": (cells[4].inner_text() or "").strip(),
                        "centro_instruccion": (cells[5].inner_text() or "").strip(),
                        "fecha_reporte": (cells[6].inner_text() or "").strip(),
                        "estado": (cells[7].inner_text() or "").strip(),
                    }
                    historial.append(record)

            logger.info("Parsed %d historial records", len(historial))

        except Exception as e:
            logger.warning("Could not parse historial: %s", e)

        return historial
