"""Bolívar vehicle tax source."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

# The root redirects to /gobol_web — liquidaciones page has the vehicle query form
SOURCE_URL = "https://impuestos.bolivar.gov.co/gobol_web/liquidaciones"
SOURCE_NAME = "co.impuesto_vehicular_bolivar"


@register
class ImpuestoVehicularBolivarSource(ImpuestoVehicularBaseSource):
    """Query Bolívar vehicle tax portal.

    Custom Laravel app. The liquidaciones page has:
    - Form id="frmLiquidacion", action="/gobol_web/liquidaciones/consultar-vehiculo"
    - Input name="placa", id="placa"
    - Submit button inside .input-group-append
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Bolívar"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Bolívar",
            description="Vehicle tax debt query for Bolívar department",
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

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector(self._source_name, "placa", placa)

        with browser.page(self._source_url, wait_until="networkidle") as page:
            try:
                if collector:
                    collector.attach(page)

                placa_input = page.locator("input#placa")
                placa_input.wait_for(state="visible", timeout=15000)
                placa_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit the liquidacion form
                page.locator("form#frmLiquidacion button[type='submit'], "
                             "form#frmLiquidacion .input-group-append button").first.click()
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
