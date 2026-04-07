"""Santander vehicle tax source — IUVA SyC (Edesk/PRISMA)."""

from __future__ import annotations

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult
from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://iuva.syc.com.co/santander"
SOURCE_NAME = "co.impuesto_vehicular_santander"


@register
class ImpuestoVehicularSantanderSource(ImpuestoVehicularBaseSource):
    """Query Santander vehicle tax portal (IUVA/Edesk/PRISMA).

    Edesk/PRISMA SPA platform (SyC Ingeniería). The public-facing "pendientes"
    module requires a captcha + document/placa to look up tax debts.
    The SYCaptcha image CAPTCHA is present on the public query form.
    """

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Santander"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Santander (IUVA)",
            description="Vehicle tax debt query for Santander department via IUVA system",
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

                # The PRISMA/Edesk SPA (SyC Ingeniería) loads the PendientesPagar module
                # dynamically. Wait for the platform to initialise, then attempt to
                # navigate directly to the public pendientes panel via the hash route.
                page.wait_for_timeout(4000)

                # Try navigating to the direct pendientes public route
                try:
                    page.evaluate("window.location.hash = '#/publico/pendientes'")
                    page.wait_for_timeout(2000)
                except Exception:
                    pass

                # Try to activate the PendientesPagar panel via menu click if visible
                for menu_sel in [
                    "a:has-text('Pendientes')", "a:has-text('Pagar')",
                    "a:has-text('Vehiculo')", "a:has-text('Vehículo')",
                    "[data-panel='PendientesPagar']", ".menu-item:has-text('Pendientes')",
                ]:
                    try:
                        loc = page.locator(menu_sel).first
                        if loc.count() and loc.is_visible():
                            loc.click()
                            page.wait_for_timeout(1500)
                            break
                    except Exception:
                        continue

                # Wait for the vehicle/placa input to appear in the pendientes form
                placa_sel = (
                    "input[name*='placa' i], input[id*='placa' i], "
                    "input[placeholder*='placa' i], input[placeholder*='Placa' i], "
                    "input[name*='vehiculo' i], input[id*='numVehiculo' i]"
                )
                placa_input = page.locator(placa_sel).first
                placa_input.wait_for(state="visible", timeout=20000)
                placa_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_sel = (
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "button:has-text('Verificar'), input[value*='Buscar' i]"
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
