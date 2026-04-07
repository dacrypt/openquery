"""Bogotá vehicle tax source — SHD Consulta Pagos."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://oficinavirtual.shd.gov.co/ConsultaPagos/ConsultaPagos.html"
SOURCE_NAME = "co.impuesto_vehicular_bogota"


@register
class ImpuestoVehicularBogotaSource(ImpuestoVehicularBaseSource):
    """Query Bogotá vehicle tax (SHD — Secretaría de Hacienda Distrital).

    AngularJS SPA with:
    - Dropdown ng-model="datos.impuesto" — must select value 3 (Vehículos)
    - Input id="placa" (shown when datos.impuesto == 3)
    - Button ng-click="consultar()"
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Bogotá D.C."
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Bogotá (SHD)",
            description="Vehicle tax debt query for Bogotá D.C. via Secretaría de Hacienda Distrital",  # noqa: E501
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

                # Wait for AngularJS to populate the impuesto dropdown (ng-options)
                # Options are loaded async — wait until at least 2 options appear
                impuesto_sel = page.locator("select.form-control").first
                impuesto_sel.wait_for(state="visible", timeout=15000)
                page.wait_for_function(
                    "document.querySelector('select.form-control') && "
                    "document.querySelector('select.form-control').options.length > 1",
                    timeout=15000,
                )
                # Select by label text "Vehículos" (fallback to value "3")
                try:
                    impuesto_sel.select_option(label="Vehículos")
                except Exception:
                    impuesto_sel.select_option(value="3")
                page.wait_for_timeout(800)

                # Fill the placa input (shown when datos.impuesto == vehicle type)
                placa_input = page.locator("input#placa")
                placa_input.wait_for(state="visible", timeout=10000)
                placa_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click Consultar — button[type='button'] with ng-click="consultar()"
                consultar_btn = page.locator(
                    "button.btn-success, button[ng-click*='consultar']"
                ).first
                consultar_btn.wait_for(state="visible", timeout=10000)
                consultar_btn.click()
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
