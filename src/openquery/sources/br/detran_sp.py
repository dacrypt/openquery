"""Brazil DETRAN-SP source — São Paulo vehicle debt lookup.

Queries São Paulo DETRAN portal for vehicle situation and debts
(IPVA, licensing fees, fines) by license plate and RENAVAM.
Browser-based, no login required.

Source: https://www.detran.sp.gov.br/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.detran_sp import DetranSpResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DETRAN_SP_URL = "https://www.detran.sp.gov.br/wps/portal/portaldetran/cidadao/veiculos/consultaDebitoVeiculo/debitoVeiculo"


@register
class DetranSpSource(BaseSource):
    """Query São Paulo DETRAN for vehicle debts and situation."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.detran_sp",
            display_name="DETRAN-SP — Débitos de Veículos (São Paulo)",
            description="São Paulo vehicle debt lookup: IPVA, licensing, fines, situation (DETRAN-SP)",
            country="BR",
            url=DETRAN_SP_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        placa = input.extra.get("placa", "") or input.document_number
        renavam = input.extra.get("renavam", "")
        if not placa:
            raise SourceError("br.detran_sp", "License plate (placa) is required")
        placa_clean = placa.upper().replace("-", "").replace(" ", "").strip()
        return self._query(placa_clean, renavam.strip(), audit=input.audit)

    def _query(self, placa: str, renavam: str = "", audit: bool = False) -> DetranSpResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("br.detran_sp", "placa", placa)

        with browser.page(DETRAN_SP_URL) as page:
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
                    raise SourceError("br.detran_sp", "Could not find plate input field")

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
                raise SourceError("br.detran_sp", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str, renavam: str) -> DetranSpResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = DetranSpResult(queried_at=datetime.now(), placa=placa, renavam=renavam)

        details: dict[str, str] = {}
        lines = body_text.split("\n")

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            if not stripped:
                continue

            # Vehicle description
            if any(k in lower for k in ("marca", "modelo", "ano", "cor", "chassi")):
                if ":" in stripped:
                    key, _, val = stripped.partition(":")
                    details[key.strip()] = val.strip()
                    if not result.vehicle_description and any(
                        k in lower for k in ("modelo", "marca")
                    ):
                        result.vehicle_description = val.strip()

            # IPVA status
            if "ipva" in lower and ":" in stripped:
                val = stripped.split(":", 1)[1].strip()
                if not result.ipva_status:
                    result.ipva_status = val

            # Licensing status
            if any(k in lower for k in ("licenciamento", "licença")) and ":" in stripped:
                val = stripped.split(":", 1)[1].strip()
                if not result.licensing_status:
                    result.licensing_status = val

            # Total debt
            if any(k in lower for k in ("total", "débito", "debito")) and "r$" in lower:
                if ":" in stripped:
                    val = stripped.split(":", 1)[1].strip()
                    if not result.total_debt:
                        result.total_debt = val
                elif not result.total_debt and "r$" in stripped:
                    result.total_debt = stripped

            # Fines count
            if any(k in lower for k in ("multa", "infração", "infracao")):
                import re
                nums = re.findall(r"\d+", stripped)
                if nums and result.fines_count == 0:
                    result.fines_count = int(nums[0])

        result.details = details
        return result
