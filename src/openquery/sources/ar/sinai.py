"""SINAI source — Argentine national traffic infractions (ANSV).

Agencia Nacional de Seguridad Vial — Sistema Nacional de Antecedentes de Tránsito.

Queries SINAI for traffic infractions by plate (patente/dominio) from
SINAI-adhered jurisdictions.

Flow:
1. Navigate to ANSV infraction consultation portal
2. Enter plate (dominio)
3. Solve CAPTCHA if present
4. Submit and parse infraction list
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.sinai import SinaiInfraction, SinaiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SINAI_URL = "https://consultainfracciones.seguridadvial.gob.ar/"


@register
class SinaiSource(BaseSource):
    """Query Argentine SINAI for traffic infractions by plate (dominio)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.sinai",
            display_name="SINAI — Infracciones de Tránsito (ANSV)",
            description=(
                "Argentine national traffic infractions from SINAI-adhered jurisdictions "
                "by plate (dominio)"
            ),
            country="AR",
            url=SINAI_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError("ar.sinai", f"Unsupported document type: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, dominio: str, audit: bool = False) -> SinaiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.sinai", "placa", dominio)

        with browser.page(SINAI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Find plate input field
                plate_input = page.query_selector(
                    'input[name*="dominio" i], input[name*="patente" i], '
                    'input[placeholder*="dominio" i], input[placeholder*="patente" i], '
                    'input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("ar.sinai", "Could not find plate input field")

                plate_input.fill(dominio.upper())
                logger.info("Filled dominio: %s", dominio)

                # Solve CAPTCHA if present
                captcha_img = page.query_selector(
                    'img[alt*="captcha" i], img[alt*="verificador" i], '
                    '.captcha img, #captcha img'
                )
                captcha_input = page.query_selector(
                    'input[name*="captcha" i], input[placeholder*="captcha" i], '
                    'input[id*="captcha" i]'
                )
                if captcha_img and captcha_input:
                    from openquery.core.captcha import ChainedSolver, LLMCaptchaSolver, OCRSolver

                    solvers = []
                    try:
                        solvers.append(LLMCaptchaSolver())
                    except Exception:
                        pass
                    solvers.append(OCRSolver(max_chars=6))
                    chain = ChainedSolver(solvers)
                    for attempt in range(1, 4):
                        try:
                            image_bytes = captcha_img.screenshot()
                            if image_bytes and len(image_bytes) >= 100:
                                text = chain.solve(image_bytes)
                                if text:
                                    captcha_input.fill(text)
                                    logger.info("CAPTCHA solved (attempt %d): %s", attempt, text)
                                    break
                        except Exception as e:
                            logger.warning("CAPTCHA attempt %d failed: %s", attempt, e)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit = page.query_selector(
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[type="submit"], button[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    plate_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dominio)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.sinai", f"Query failed: {e}") from e

    def _parse_result(self, page, dominio: str) -> SinaiResult:
        body_text = page.inner_text("body")
        result = SinaiResult(placa=dominio.upper())

        infractions: list[SinaiInfraction] = []

        # Parse infraction rows from table
        rows = page.query_selector_all("table tr, .infraction-row, .resultado tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                infraction = SinaiInfraction(
                    date=(cells[0].inner_text() or "").strip(),
                    description=(cells[1].inner_text() or "").strip(),
                    amount=(cells[2].inner_text() or "").strip(),
                    status=(cells[3].inner_text() or "").strip() if len(cells) > 3 else "",
                )
                if infraction.description:
                    infractions.append(infraction)

        result.infractions = infractions
        result.total_infractions = len(infractions)
        result.details = {"raw_text": body_text[:500] if body_text else ""}

        return result
