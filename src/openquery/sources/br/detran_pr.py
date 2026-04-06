"""Brazil DETRAN-PR source — Paraná vehicle lookup.

Queries Paraná DETRAN portal for vehicle situation by license plate.
Browser-based, no login required.

Source: https://www.detran.pr.gov.br/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.detran_pr import DetranPrResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DETRAN_PR_URL = "https://www.detran.pr.gov.br/Noticia/Consultar-Veiculos"


@register
class DetranPrSource(BaseSource):
    """Query Paraná DETRAN for vehicle situation by license plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.detran_pr",
            display_name="DETRAN-PR — Consulta de Veículos (Paraná)",
            description="Paraná vehicle situation lookup by license plate (DETRAN-PR)",
            country="BR",
            url=DETRAN_PR_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        placa = input.extra.get("placa", "") or input.document_number
        if not placa:
            raise SourceError("br.detran_pr", "License plate (placa) is required")
        placa_clean = placa.upper().replace("-", "").replace(" ", "").strip()
        return self._query(placa_clean, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> DetranPrResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.detran_pr", "placa", placa)

        with browser.page(DETRAN_PR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                placa_input = page.query_selector(
                    'input[name*="placa" i], input[id*="placa" i], '
                    'input[placeholder*="placa" i], input[type="text"]'
                )
                if not placa_input:
                    raise SourceError("br.detran_pr", "Could not find plate input field")

                placa_input.fill(placa)
                logger.info("Filled placa: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button[id*="consultar" i], input[value*="Consultar"]'
                )
                if submit:
                    submit.click()
                else:
                    placa_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, placa)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.detran_pr", f"Query failed: {e}") from e

    def _parse_result(self, page: object, placa: str) -> DetranPrResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        result = DetranPrResult(queried_at=datetime.now(), placa=placa)
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_clean = key.strip()
            val_clean = val.strip()
            if val_clean:
                details[key_clean] = val_clean

            if any(k in lower for k in ("marca", "modelo", "ano", "cor")):
                if not result.vehicle_description and val_clean:
                    result.vehicle_description = val_clean

            if any(k in lower for k in ("situação", "situacao", "status", "situaç")):
                if not result.situation and val_clean:
                    result.situation = val_clean

        result.details = details
        return result
