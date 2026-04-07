"""Huila vehicle tax source."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://vehiculos.huila.gov.co/HUIVehiculos/IUVA_001.jsp"
SOURCE_NAME = "co.impuesto_vehicular_huila"


@register
class ImpuestoVehicularHuilaSource(ImpuestoVehicularBaseSource):
    """Query Huila vehicle tax portal.

    JSP application with an expired SSL certificate (ERR_CERT_DATE_INVALID).
    Requires ignore_https_errors=True in browser context.

    Form: id="commentForm", action="/HUIVehiculos/BuscarPlaca.do"
    - Input: name="txt_NumPlaca", id="txt_NumPlaca"
    - Submit: input[type='submit'][value='Buscar']
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Huila"
    _needs_documento = True

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Huila",
            description="Vehicle tax debt query for Huila department",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def _query(
        self, placa: str, documento: str = "", audit: bool = False
    ) -> ImpuestoVehicularResult:
        from openquery.core.browser import BrowserManager

        # ignore_https_errors bypasses the expired SSL cert on vehiculos.huila.gov.co
        browser = BrowserManager(
            headless=self._headless,
            timeout=self._timeout,
            ignore_https_errors=True,
        )
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector(self._source_name, "placa", placa)

        with browser.page(self._source_url, wait_until="networkidle") as page:
            try:
                if collector:
                    collector.attach(page)

                placa_input = page.locator("input#txt_NumPlaca")
                placa_input.wait_for(state="visible", timeout=15000)
                placa_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.locator(
                    "input[type='submit'][value='Buscar'], input[type='submit'].btn-success"
                )
                submit_btn.wait_for(state="visible", timeout=10000)
                submit_btn.first.click()
                page.wait_for_load_state("networkidle", timeout=25000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, placa)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(self._source_name, f"Query failed: {e}") from e
