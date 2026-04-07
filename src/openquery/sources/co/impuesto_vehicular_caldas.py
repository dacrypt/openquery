"""Caldas vehicle tax source."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://rentas.caldas.gov.co/"
# vehiculos.caldas.gov.co/web/ redirects to rentas.caldas.gov.co
SOURCE_NAME = "co.impuesto_vehicular_caldas"


@register
class ImpuestoVehicularCaldasSource(ImpuestoVehicularBaseSource):
    """Query Caldas vehicle tax portal (SISCAR / Portal Tributario).

    Angular SPA at rentas.caldas.gov.co (vehiculos.caldas.gov.co/web/ redirects here).
    Uses Angular Reactive Forms with formControlName bindings.
    The placa field validates 5-8 alphanumeric characters.
    Has reCAPTCHA — stealth browser may bypass.
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Caldas"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Caldas",
            description="Vehicle tax debt query for Caldas department",
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

                # SISCAR Angular SPA — wait for <app-root> to render the public
                # vehicle lookup form. Uses Angular Reactive Forms (formControlName).
                page.wait_for_selector("app-root", timeout=15000)
                page.wait_for_timeout(3000)

                # The placa input may be inside a mat-form-field with formControlName
                placa_input = page.locator(
                    "input[formcontrolname*='placa' i], "
                    "input[placeholder*='placa' i], input[placeholder*='Placa' i], "
                    "input[name*='placa' i], input[id*='placa' i], "
                    "app-root input[type='text']:visible"
                ).first
                placa_input.wait_for(state="visible", timeout=20000)
                placa_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Try submit button variants common to Angular Material + SISCAR
                submitted = False
                for sel in [
                    "button[type='submit']",
                    "input[type='submit']",
                    "button:has-text('Consultar')",
                    "button:has-text('Liquidar')",
                    "button:has-text('Buscar')",
                    "button:has-text('Verificar')",
                ]:
                    try:
                        loc = page.locator(sel).first
                        if loc.count() and loc.is_visible():
                            loc.click()
                            submitted = True
                            break
                    except Exception:
                        continue
                if not submitted:
                    placa_input.press("Enter")

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
