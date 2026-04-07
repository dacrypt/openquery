"""Meta vehicle tax source."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

# Root redirects to /portal-meta/
SOURCE_URL = "https://impuestovehicular.meta.gov.co/portal-meta/"
SOURCE_NAME = "co.impuesto_vehicular_meta"


@register
class ImpuestoVehicularMetaSource(ImpuestoVehicularBaseSource):
    """Query Meta vehicle tax portal.

    Angular SPA (Portal Impuesto Vehicular platform, same as Narino).
    Form field: input[name='placa'] with Cloudflare Turnstile + reCAPTCHA.
    After submit navigates to /vehiculo/{placa}/1 route.
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Meta"
    _needs_documento = True

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Meta",
            description="Vehicle tax debt query for Meta department",
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
                # Same platform as Nariño: ngModel="placa_vehi", ngSubmit="liquidarVehiculo()".
                # Meta additionally has Cloudflare Turnstile + Zenedge bot detection.
                page.wait_for_selector(
                    "app-root input[type='text'], app-root input:not([type])", timeout=25000
                )

                # Select Colombia in the País dropdown (first select in form)
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
                placa_input.press("Tab")

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit via Liquidar button or Enter key fallback
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
