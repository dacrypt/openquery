"""Venezuela CICPC source — criminal records lookup.

Queries Venezuela's CICPC (Cuerpo de Investigaciones Científicas,
Penales y Criminalísticas) for criminal background status by cedula.

Source: https://www.cicpc.gob.ve/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.cicpc import CicpcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CICPC_URL = "https://www.cicpc.gob.ve/"


@register
class CicpcSource(BaseSource):
    """Query Venezuela CICPC criminal records by cedula."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.cicpc",
            display_name="CICPC — Antecedentes Penales",
            description=(
                "Venezuela criminal records: background status by cedula"
                " (Cuerpo de Investigaciones Científicas, Penales y Criminalísticas)"
            ),
            country="VE",
            url=CICPC_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "ve.cicpc",
                f"Unsupported document type: {input.document_type}. Use cedula.",
            )
        cedula = input.document_number.strip()
        if not cedula:
            raise SourceError("ve.cicpc", "cedula is required")
        return self._query(cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> CicpcResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ve.cicpc", "cedula", cedula)

        with browser.page(CICPC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Determine V/E prefix
                cedula_upper = cedula.upper()
                if cedula_upper.startswith("V") or cedula_upper.startswith("E"):
                    prefix = cedula_upper[0]
                    number = cedula_upper[1:].lstrip("-").strip()
                else:
                    prefix = "V"
                    number = cedula.strip()

                # Select nationality prefix if dropdown present
                try:
                    prefix_select = page.query_selector(
                        'select[name*="nac"], select[name*="nacionalidad"], select[id*="nac"]'
                    )
                    if prefix_select:
                        prefix_select.select_option(value=prefix)
                except Exception:
                    pass

                cedula_input = page.query_selector(
                    'input[name*="cedula"], input[name*="numero"], '
                    'input[id*="cedula"], input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("ve.cicpc", "Could not find cedula input field")

                cedula_input.fill(number)
                logger.info("Querying CICPC for cedula: %s%s", prefix, number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.cicpc", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> CicpcResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = CicpcResult(queried_at=datetime.now(), cedula=cedula)

        criminal_status = ""
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_lower = key.strip().lower()
            val_clean = val.strip()
            if not val_clean:
                continue
            details[key.strip()] = val_clean
            if (
                "antecedente" in key_lower
                or "registro" in key_lower
                or "estado" in key_lower
                or "status" in key_lower
                or "resultado" in key_lower
            ) and not criminal_status:
                criminal_status = val_clean

        # Fallback: try table rows
        if not criminal_status:
            rows = page.query_selector_all("table tr, .resultado tr, .info-row")
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                if (
                    "antecedente" in text_lower
                    or "resultado" in text_lower
                    or "estado" in text_lower
                ) and ":" in text:
                    criminal_status = text.split(":", 1)[1].strip()
                    break

        result.criminal_status = criminal_status
        result.details = details
        return result
