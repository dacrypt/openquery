"""CNE source — Venezuela electoral registry / cedula lookup.

Queries the CNE (Consejo Nacional Electoral) voter registry for a cedula.

Flow:
1. Navigate to CNE electoral registry page
2. Enter cedula (V/E prefix + number)
3. Submit form and parse full name, voting center, municipality, state

Source: http://www.cne.gob.ve/web/registro_electoral/registro_electoral.php
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.cne import CneResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CNE_URL = "http://www.cne.gob.ve/web/registro_electoral/registro_electoral.php"


@register
class CneSource(BaseSource):
    """Query Venezuela electoral registry by cedula (CNE)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.cne",
            display_name="CNE — Registro Electoral",
            description=(
                "Venezuela electoral registry: full name, voting center, municipality, state"
            ),
            country="VE",
            url=CNE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "ve.cne",
                f"Unsupported document type: {input.document_type}. Use cedula.",
            )
        cedula = input.document_number.strip()
        if not cedula:
            raise SourceError("ve.cne", "cedula is required")
        return self._query(cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> CneResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ve.cne", "cedula", cedula)

        with browser.page(CNE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Determine prefix (V or E) from cedula input
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

                # Fill cedula number
                cedula_input = page.query_selector(
                    'input[name*="cedula"], input[name*="numero"], '
                    'input[id*="cedula"], input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("ve.cne", "Could not find cedula input field")

                cedula_input.fill(number)
                logger.info("Querying CNE for cedula: %s%s", prefix, number)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"]'
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
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.cne", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> CneResult:
        """Parse CNE result page for voter information."""
        from datetime import datetime

        body_text = page.inner_text("body")

        nombre = ""
        centro_votacion = ""
        municipio = ""
        estado = ""
        details: dict[str, str] = {}

        label_map = {
            "nombre": ("nombre",),
            "nombres": ("nombre",),
            "centro": ("centro_votacion",),
            "municipio": ("municipio",),
            "estado": ("estado",),
            "parroquia": (),
        }

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

            for label, fields in label_map.items():
                if label in key_lower:
                    if "nombre" in fields and not nombre:
                        nombre = val_clean
                    elif "centro_votacion" in fields and not centro_votacion:
                        centro_votacion = val_clean
                    elif "municipio" in fields and not municipio:
                        municipio = val_clean
                    elif "estado" in fields and not estado:
                        estado = val_clean

        # Fallback: try table rows
        if not nombre:
            rows = page.query_selector_all("table tr, .resultado tr, .info-row")
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                if "nombre" in text_lower and ":" in text and not nombre:
                    nombre = text.split(":", 1)[1].strip()
                elif "centro" in text_lower and ":" in text and not centro_votacion:
                    centro_votacion = text.split(":", 1)[1].strip()
                elif "municipio" in text_lower and ":" in text and not municipio:
                    municipio = text.split(":", 1)[1].strip()
                elif "estado" in text_lower and ":" in text and not estado:
                    estado = text.split(":", 1)[1].strip()

        return CneResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            centro_votacion=centro_votacion,
            municipio=municipio,
            estado=estado,
            details=details,
        )
