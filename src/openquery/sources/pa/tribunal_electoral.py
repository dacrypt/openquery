"""Panama Tribunal Electoral source — identity verification.

Queries Panama's Tribunal Electoral portal to verify cedula identity.
Browser-based, no login required, public access.

Portal: https://verificate.te.gob.pa/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.tribunal_electoral import TribunalElectoralResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PORTAL_URL = "https://verificate.te.gob.pa/"


@register
class TribunalElectoralSource(BaseSource):
    """Query Panama Tribunal Electoral for cedula identity verification."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.tribunal_electoral",
            display_name="Tribunal Electoral — Verificación de Cédula",
            description=(
                "Panama identity verification via Tribunal Electoral (verificate.te.gob.pa)"
            ),
            country="PA",
            url=PORTAL_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "pa.tribunal_electoral",
                f"Only cedula supported, got: {input.document_type}",
            )
        cedula = input.document_number.strip()
        if not cedula:
            raise SourceError("pa.tribunal_electoral", "Cedula number is required")
        return self._query(cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> TribunalElectoralResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pa.tribunal_electoral", "cedula", cedula)

        with browser.page(PORTAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Find cedula input
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"][placeholder*="edula"], '
                    'input[type="number"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("pa.tribunal_electoral", "Could not find cedula input field")

                cedula_input.fill(cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button[id*="verificar"], button[class*="btn-primary"], '
                    "button"
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(3000)

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
                raise SourceError("pa.tribunal_electoral", f"Query failed: {e}") from e

    def _parse_result(self, page: object, cedula: str) -> TribunalElectoralResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()

        nombre = ""
        estado = ""
        circuito = ""
        corregimiento = ""
        centro_votacion = ""
        mesa = ""
        details: dict[str, str] = {}

        # Detect not found
        if any(phrase in body_lower for phrase in ("no se encontr", "no registra", "no existe")):
            estado = "No registrada"
            return TribunalElectoralResult(
                queried_at=datetime.now(),
                cedula=cedula,
                estado=estado,
                details=details,
            )

        # Parse key-value lines
        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_clean = key.strip().lower()
            val_clean = val.strip()

            if not val_clean:
                continue

            details[key.strip()] = val_clean

            if any(k in key_clean for k in ("nombre", "name")):
                nombre = val_clean
            elif "estado" in key_clean or "status" in key_clean:
                estado = val_clean
            elif "circuito" in key_clean:
                circuito = val_clean
            elif "corregimiento" in key_clean:
                corregimiento = val_clean
            elif "centro" in key_clean and "votac" in key_clean:
                centro_votacion = val_clean
            elif "mesa" in key_clean:
                mesa = val_clean

        # Fallback estado detection
        if not estado:
            if "vigente" in body_lower or "habilitado" in body_lower or "activo" in body_lower:
                estado = "Vigente"
            elif "cancelad" in body_lower or "inhabilitad" in body_lower:
                estado = "Cancelada"

        return TribunalElectoralResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            estado=estado,
            circuito=circuito,
            corregimiento=corregimiento,
            centro_votacion=centro_votacion,
            mesa=mesa,
            details=details,
        )
