"""Cundinamarca vehicle tax source — SIVER."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://impuvehiculo.cundinamarca.gov.co/sivervcundinamarca/redirect/primeracert.php"
SOURCE_NAME = "co.impuesto_vehicular_cundinamarca"


@register
class ImpuestoVehicularCundinamarcaSource(ImpuestoVehicularBaseSource):
    """Query Cundinamarca vehicle tax portal (SIVER).

    The SIVER Cundinamarca portal has a form at the redirect URL with:
    - Input field: name="numero" (placa)
    - Submit button: name="agregar", value="Consultar"
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Cundinamarca"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Cundinamarca (SIVER)",
            description="Vehicle tax debt query for Cundinamarca department via SIVER system",
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

                # SIVER Cundinamarca: field name="numero", submit name="agregar"
                numero_input = page.locator("input[name='numero']")
                numero_input.wait_for(state="visible", timeout=15000)
                numero_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                page.locator("input[name='agregar']").click()
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
