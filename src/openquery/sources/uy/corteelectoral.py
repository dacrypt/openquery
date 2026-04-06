"""Uruguay Corte Electoral source — voter registry.

Queries the Corte Electoral for voter status, polling location, and
habilitado status by credential series and number.

Source: https://aplicaciones.corteelectoral.gub.uy/buscadorpermanente/buscadores.buscadorpermanente.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.corteelectoral import UyCorteElectoralResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CORTE_URL = (
    "https://aplicaciones.corteelectoral.gub.uy/buscadorpermanente/"
    "buscadores.buscadorpermanente.aspx"
)


@register
class UyCorteElectoralSource(BaseSource):
    """Query Uruguayan Corte Electoral voter registry by credential."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.corteelectoral",
            display_name="Corte Electoral — Padrón Electoral",
            description="Uruguay voter registry: habilitado status, polling location (Corte Electoral)",
            country="UY",
            url=CORTE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        credencial = input.document_number or input.extra.get("credencial", "")
        if not credencial:
            raise SourceError("uy.corteelectoral", "Credencial (series + number) is required")
        return self._query(credencial.strip(), audit=input.audit)

    def _query(self, credencial: str, audit: bool = False) -> UyCorteElectoralResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("uy.corteelectoral", "custom", credencial)

        with browser.page(CORTE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cred_input = page.query_selector(
                    'input[name*="credencial"], input[id*="credencial"], '
                    'input[name*="serie"], input[id*="serie"], '
                    'input[type="text"]'
                )
                if not cred_input:
                    raise SourceError("uy.corteelectoral", "Could not find credencial input field")

                cred_input.fill(credencial)
                logger.info("Filled credencial: %s", credencial)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    cred_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, credencial)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.corteelectoral", f"Query failed: {e}") from e

    def _parse_result(self, page, credencial: str) -> UyCorteElectoralResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = UyCorteElectoralResult(queried_at=datetime.now(), credencial=credencial)

        field_map = {
            "nombre": "nombre",
            "habilitado": "habilitado",
            "local": "lugar_votacion",
            "lugar": "lugar_votacion",
            "establecimiento": "lugar_votacion",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and (":" in stripped or "\t" in stripped):
                    sep = ":" if ":" in stripped else "\t"
                    value = stripped.split(sep, 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
