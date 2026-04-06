"""Brazil DETRAN-RJ source — Rio de Janeiro vehicle lookup.

Queries Rio de Janeiro DETRAN portal for vehicle situation and debts
by license plate and RENAVAM.
Browser-based, no login required.

Source: https://www.detran.rj.gov.br/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.detran_rj import DetranRjResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DETRAN_RJ_URL = "https://www.detran.rj.gov.br/_monta_aplicacoes.asp?cod=22&tipo=consulta_veiculo"


@register
class DetranRjSource(BaseSource):
    """Query Rio de Janeiro DETRAN for vehicle situation and debts."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.detran_rj",
            display_name="DETRAN-RJ — Consulta de Veículo (Rio de Janeiro)",
            description="Rio de Janeiro vehicle lookup: situation, debts by plate and RENAVAM (DETRAN-RJ)",  # noqa: E501
            country="BR",
            url=DETRAN_RJ_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        placa = input.extra.get("placa", "") or input.document_number
        renavam = input.extra.get("renavam", "")
        if not placa:
            raise SourceError("br.detran_rj", "License plate (placa) is required")
        placa_clean = placa.upper().replace("-", "").replace(" ", "").strip()
        return self._query(placa_clean, renavam.strip(), audit=input.audit)

    def _query(self, placa: str, renavam: str = "", audit: bool = False) -> DetranRjResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.detran_rj", "placa", placa)

        with browser.page(DETRAN_RJ_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate
                placa_input = page.query_selector(
                    'input[name*="placa" i], input[id*="placa" i], '
                    'input[placeholder*="placa" i], input[type="text"]'
                )
                if not placa_input:
                    raise SourceError("br.detran_rj", "Could not find plate input field")

                placa_input.fill(placa)
                logger.info("Filled placa: %s", placa)

                # Fill RENAVAM if provided
                if renavam:
                    renavam_input = page.query_selector(
                        'input[name*="renavam" i], input[id*="renavam" i], '
                        'input[placeholder*="renavam" i]'
                    )
                    if renavam_input:
                        renavam_input.fill(renavam)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
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

                result = self._parse_result(page, placa, renavam)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.detran_rj", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str, renavam: str) -> DetranRjResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = DetranRjResult(queried_at=datetime.now(), placa=placa, renavam=renavam)
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

            # Vehicle description
            if any(k in lower for k in ("marca", "modelo", "ano", "cor", "chassi")):
                if ":" in stripped and not result.vehicle_description:
                    val = stripped.split(":", 1)[1].strip()
                    if any(k in lower for k in ("modelo", "marca")):
                        result.vehicle_description = val

            # Situation
            if any(k in lower for k in ("situação", "situacao", "status", "condicao", "condição")):
                if ":" in stripped and not result.situation:
                    result.situation = stripped.split(":", 1)[1].strip()

            # Total debt
            if any(k in lower for k in ("total", "débito", "debito", "valor")) and "r$" in lower:
                if ":" in stripped and not result.total_debt:
                    result.total_debt = stripped.split(":", 1)[1].strip()
                elif not result.total_debt and "r$" in stripped:
                    result.total_debt = stripped

        result.details = details
        return result
