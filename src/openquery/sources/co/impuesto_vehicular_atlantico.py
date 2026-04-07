"""Atlántico vehicle tax source — Portal Impuestos Atlántico."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://portalimpuestos.atlantico.gov.co/apps/vehiculos/consulta"
# Navigate directly to the vehicle consulta page (root redirects to dashboard)
SOURCE_NAME = "co.impuesto_vehicular_atlantico"


@register
class ImpuestoVehicularAtlanticoSource(ImpuestoVehicularBaseSource):
    """Query Atlántico vehicle tax portal.

    Next.js SSR portal with reCAPTCHA Enterprise at portalimpuestos.atlantico.gov.co.
    Direct URL: /apps/vehiculos/consulta
    The consulta page has a placa search field with a Consultar submit button.
    reCAPTCHA Enterprise (key: 6LcMy3EqAAAAAG-lvFrDSihQkHeIYL2UhOYH1o2S) is present.
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Atlántico"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Atlántico",
            description="Vehicle tax debt query for Atlántico department",
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

                # Next.js SSR — the consulta page renders client-side after hydration.
                # Wait for React to mount the vehicle query form.
                page.wait_for_timeout(4000)

                # The page has a placa text input with a Consultar button
                placa_sel = (
                    "input[name*='placa' i], input[id*='placa' i], "
                    "input[placeholder*='placa' i], "
                    "input[placeholder*='Placa' i], input[placeholder*='PLACA' i], "
                    "input[type='text']:visible"
                )
                placa_input = page.locator(placa_sel).first
                placa_input.wait_for(state="visible", timeout=20000)
                placa_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — reCAPTCHA Enterprise present; stealth browser may bypass
                submitted = False
                for sel in [
                    "button[type='submit']",
                    "button:has-text('Consultar')",
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
