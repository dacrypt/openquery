"""Norte de Santander vehicle tax source."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

# The root redirects to /Declaracion-impuesto-vehicular.aspx
SOURCE_URL = "https://vehiculos.nortedesantander.gov.co/"
SOURCE_NAME = "co.impuesto_vehicular_norte_santander"


@register
class ImpuestoVehicularNorteSantanderSource(ImpuestoVehicularBaseSource):
    """Query Norte de Santander vehicle tax portal.

    ASP.NET WebForms portal. The main page has:
    - Input id="ContentPlaceHolder1_TxtPlaca" (name="ctl00$ContentPlaceHolder1$TxtPlaca")
    - Link button id="ContentPlaceHolder1_LinkConsultar" — triggers postback
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Norte de Santander"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Norte de Santander",
            description="Vehicle tax debt query for Norte de Santander department",
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

                placa_input = page.locator("#ContentPlaceHolder1_TxtPlaca")
                placa_input.wait_for(state="visible", timeout=15000)
                placa_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click the "Consultar Placa" link-button (ASP.NET postback)
                page.locator("#ContentPlaceHolder1_LinkConsultar").click()
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
