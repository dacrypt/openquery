"""Risaralda vehicle tax source."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

# Root redirects to /impuestosweb — navigate there directly
SOURCE_URL = "https://vehiculos.risaralda.gov.co/impuestosweb"
SOURCE_NAME = "co.impuesto_vehicular_risaralda"


@register
class ImpuestoVehicularRisaraldaSource(ImpuestoVehicularBaseSource):
    """Query Risaralda vehicle tax portal.

    Quipux AngularJS SPA at vehiculos.risaralda.gov.co/impuestosweb.
    Uses Cloudflare Turnstile + hCaptcha protection.
    Longer wait required for SPA initialization before form is visible.
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Risaralda"
    _needs_documento = True

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Risaralda",
            description="Vehicle tax debt query for Risaralda department",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
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

        with browser.page(self._source_url, wait_until="domcontentloaded") as page:
            try:
                if collector:
                    collector.attach(page)

                # Quipux Innova AngularJS SPA — $MostrarConsultaGeneral = true means the
                # public consulta-general route is enabled. Navigate there via hash routing.
                page.wait_for_timeout(3000)
                try:
                    page.evaluate("window.location.hash = '#/publico/consulta-general'")
                    page.wait_for_timeout(2000)
                except Exception:
                    pass

                # Wait for consulta-general form with placa input
                placa_sel = (
                    "input[name='placa'], input[id='placa'], "
                    "input[ng-model*='placa' i], input[placeholder*='placa' i], "
                    "input[placeholder*='Placa' i], input[placeholder*='PLACA' i]"
                )
                placa_input = page.locator(placa_sel).first
                placa_input.wait_for(state="visible", timeout=20000)
                placa_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_sel = (
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "button[ng-click*='consultar' i], input[value*='Consultar' i]"
                )
                page.locator(submit_sel).first.click()
                page.wait_for_load_state("networkidle", timeout=30000)

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
