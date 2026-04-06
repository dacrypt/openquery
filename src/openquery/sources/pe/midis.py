"""MIDIS social programs beneficiary source — Peru.

Queries MIDIS for social program beneficiary status by DNI.

URL: https://www.midis.gob.pe/
Input: DNI
Returns: beneficiary status, programs
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.midis import MidisResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MIDIS_URL = "https://www.midis.gob.pe/index.php/es/informacion/consulta-de-beneficiarios"


@register
class MidisSource(BaseSource):
    """Query MIDIS for social program beneficiary status by DNI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.midis",
            display_name="MIDIS — Beneficiarios de Programas Sociales",
            description="Peru MIDIS: social program beneficiary status lookup by DNI",
            country="PE",
            url=MIDIS_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dni = (input.extra.get("dni", "") or input.document_number).strip()
        if not dni:
            raise SourceError("pe.midis", "DNI required (extra.dni or document_number)")
        return self._fetch(dni, audit=input.audit)

    def _fetch(self, dni: str, audit: bool = False) -> MidisResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying MIDIS: dni=%s", dni)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(MIDIS_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='dni'], input[name*='documento'], input[type='text']"
                )
                if search_input:
                    search_input.fill(dni)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_text.lower()

                nombre = ""
                programs = []

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if "nombre" in lower and ":" in stripped and not nombre:
                        nombre = stripped.split(":", 1)[1].strip()
                    for prog in ["pension 65", "juntos", "qali warma", "contigo", "cuna más", "haku wiñay"]:  # noqa: E501
                        if prog in lower and prog not in [p.lower() for p in programs]:
                            programs.append(stripped)

            return MidisResult(
                queried_at=datetime.now(),
                dni=dni,
                nombre=nombre,
                programs=programs,
                details=f"MIDIS query for DNI: {dni}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pe.midis", f"Query failed: {e}") from e
