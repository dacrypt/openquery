"""Nariño vehicle tax source."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

# Root redirects to /portal-narino/
SOURCE_URL = "https://impuestovehicular.narino.gov.co/portal-narino/"
SOURCE_NAME = "co.impuesto_vehicular_narino"


@register
class ImpuestoVehicularNarinoSource(ImpuestoVehicularBaseSource):
    """Query Nariño vehicle tax portal.

    Angular SPA (Portal Impuesto Vehicular platform).
    Form field: input[name='placa'] (ngModel bound to placa_vehi).
    Has reCAPTCHA — stealth browser attempts bypass.
    After submit, navigates to /vehiculo/{placa}/1 route.
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Nariño"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Nariño",
            description="Vehicle tax debt query for Nariño department",
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

                # Wait for Angular SPA (<app-root>) to render the consulta form.
                # The form uses ngModel="placa_vehi" and ngSubmit="liquidarVehiculo()".
                # First wait for any text input to appear inside app-root.
                page.wait_for_selector(
                    "app-root input[type='text'], app-root input:not([type])", timeout=20000
                )

                # Select Colombia in the País dropdown (first select in the form)
                try:
                    pais_select = page.locator("select").first
                    if pais_select.count() and pais_select.is_visible():
                        pais_select.select_option(label="Colombia")
                        page.wait_for_timeout(300)
                except Exception:
                    pass

                # Fill the placa input — ng-model bound to placa_vehi
                placa_input = page.locator(
                    "input[ng-model='placa_vehi'], input[ng-model*='placa'], "
                    "input[placeholder*='placa' i], input[placeholder*='Placa' i], "
                    "app-root input[type='text']:visible"
                ).first
                placa_input.wait_for(state="visible", timeout=15000)
                placa_input.fill(placa)
                placa_input.press("Tab")  # Trigger uppercase conversion / ng-model update

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — the form uses ngSubmit="liquidarVehiculo()" so pressing Enter
                # on the placa field or clicking the Liquidar button both work.
                # Try dedicated Liquidar button first, then Enter key fallback.
                submitted = False
                for sel in [
                    "input[type='submit']",
                    "button[type='submit']",
                    "input[value='Liquidar']",
                    "button:has-text('Liquidar')",
                    "button:has-text('Consultar')",
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
