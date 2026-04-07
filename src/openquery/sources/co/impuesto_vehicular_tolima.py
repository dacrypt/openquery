"""Tolima vehicle tax source — SIVER."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

# The redirect page is a menu — the actual form is at liquidacionweb/primeraa.php
SOURCE_URL = "https://aplicativosenlinea.net/sivervtolima/liquidacionweb/primeraa.php"
SOURCE_NAME = "co.impuesto_vehicular_tolima"


@register
class ImpuestoVehicularTolimaSource(ImpuestoVehicularBaseSource):
    """Query Tolima vehicle tax portal (SIVER).

    The SIVER Tolima liquidation form at primeraa.php has:
    - Input field: name="placa", id="placa"
    - Input field: name="documento" (document number)
    - Submit: name="agregar", value="Continuar"
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Tolima"
    _needs_documento = True

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Tolima (SIVER)",
            description="Vehicle tax debt query for Tolima department via SIVER system",
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

                # Close data protection modal if present
                try:
                    page.wait_for_timeout(1500)
                    page.evaluate("""() => {
                        const modal = document.querySelector('#modal_informativo');
                        if (modal) {
                            modal.classList.remove('show');
                            modal.style.display = 'none';
                        }
                        document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                        document.body.classList.remove('modal-open');
                    }""")
                except Exception:
                    pass

                placa_input = page.locator("input[name='placa']")
                placa_input.wait_for(state="visible", timeout=15000)
                placa_input.fill(placa)

                if documento:
                    doc_input = page.locator("input[name='documento']")
                    if doc_input.count():
                        doc_input.fill(documento)

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
