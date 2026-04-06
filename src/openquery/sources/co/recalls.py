"""Recalls source — Colombian vehicle safety recalls (SIC).

Queries the SIC (Superintendencia de Industria y Comercio) website
for vehicle safety recall campaigns.

The SIC site is known to have SSL/connectivity issues.
If the site is unreachable, a clear error with the manual URL is returned.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.recalls import RecallResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SIC_URL = (
    "https://sedeelectronica.sic.gov.co/temas/proteccion-al-consumidor/"
    "consumo-seguro/campanas-de-seguridad/automotores"
)


@register
class RecallsSource(BaseSource):
    """Query Colombian vehicle safety recalls from SIC."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.recalls",
            display_name="SIC — Campañas de Seguridad Automotores",
            description="Colombian vehicle safety recalls (SIC)",
            country="CO",
            url=SIC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query recalls by brand.

        Expects:
            input.extra["marca"] — brand name (e.g., "TESLA", "CHEVROLET")
        """
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "co.recalls",
                f"Only CUSTOM queries supported, got: {input.document_type}",
            )

        marca = input.extra.get("marca", "").upper().strip()
        if not marca:
            raise SourceError("co.recalls", "extra['marca'] is required")

        return self._query(marca, audit=input.audit)

    def _query(self, marca: str, audit: bool = False) -> RecallResult:
        """Navigate to SIC recalls page and scrape data for the given brand."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.recalls", "marca", marca)

        try:
            with browser.page(SIC_URL, wait_until="domcontentloaded") as page:
                if collector:
                    collector.attach(page)

                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    logger.warning("SIC page did not reach networkidle, continuing")

                if collector:
                    collector.screenshot(page, "page_loaded")

                # Look for brand-related links or table rows
                body_text = page.inner_text("body")

                if not body_text or len(body_text.strip()) < 100:
                    raise SourceError(
                        "co.recalls",
                        f"SIC page loaded but appears empty. Check manually: {SIC_URL}",
                    )

                # Try to find and click on the brand link/section
                campanias = self._extract_recalls(page, marca)

                result = RecallResult(
                    marca=marca,
                    total_campanias=len(campanias),
                    campanias=campanias,
                )

                if collector:
                    collector.screenshot(page, "result")
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

        except SourceError:
            raise
        except Exception as e:
            error_msg = str(e)
            if any(
                keyword in error_msg.lower()
                for keyword in [
                    "ssl",
                    "certificate",
                    "tls",
                    "connection refused",
                    "timeout",
                    "err_connection",
                    "net::err",
                ]
            ):
                raise SourceError(
                    "co.recalls",
                    f"Cannot connect to SIC website (SSL/connection error: {error_msg}). "
                    f"The SIC site has known SSL issues. "
                    f"Check manually at: {SIC_URL}",
                ) from e
            raise SourceError("co.recalls", f"Query failed: {e}") from e

    def _extract_recalls(self, page, marca: str) -> list[dict]:
        """Extract recall campaigns from the SIC page for a given brand."""
        campanias: list[dict] = []

        # Try to find links or rows matching the brand
        links = page.query_selector_all(f'a:has-text("{marca}")')
        if not links:
            # Try case-insensitive search via evaluate
            links = page.query_selector_all("a")
            links = [link for link in links if marca.lower() in (link.inner_text() or "").lower()]

        if not links:
            # Try table rows
            rows = page.query_selector_all("tr, .item, .card, .list-group-item")
            for row in rows:
                text = row.inner_text() or ""
                if marca.lower() in text.lower():
                    campanias.append(
                        {
                            "componente": "",
                            "descripcion": text.strip()[:500],
                            "anos_afectados": "",
                            "url": SIC_URL,
                        }
                    )

        for link in links[:20]:
            text = link.inner_text() or ""
            href = link.get_attribute("href") or ""

            # Try to navigate to the detail page
            try:
                if href and href.startswith("http"):
                    detail_url = href
                elif href:
                    detail_url = f"https://sedeelectronica.sic.gov.co{href}"
                else:
                    detail_url = SIC_URL

                campanias.append(
                    {
                        "componente": "",
                        "descripcion": text.strip()[:500],
                        "anos_afectados": "",
                        "url": detail_url,
                    }
                )
            except Exception as e:
                logger.warning("Failed to extract recall detail: %s", e)

        return campanias
