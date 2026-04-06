"""SENAE customs declarations source — Ecuador.

Queries SENAE for customs declaration status by declaration number.

URL: https://www.aduana.gob.ec/
Input: declaration number (custom)
Returns: status, importer
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.senae import SenaeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SENAE_URL = "https://ecuapass.aduana.gob.ec/"


@register
class SenaeSource(BaseSource):
    """Query SENAE customs declaration status by declaration number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.senae",
            display_name="SENAE — Declaraciones Aduaneras",
            description="Ecuador SENAE: customs declaration status lookup by declaration number",
            country="EC",
            url=SENAE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        declaration_number = (
            input.extra.get("declaration_number", "") or input.document_number
        ).strip()
        if not declaration_number:
            raise SourceError(
                "ec.senae",
                "Declaration number required (extra.declaration_number or document_number)",
            )
        return self._fetch(declaration_number, audit=input.audit)

    def _fetch(self, declaration_number: str, audit: bool = False) -> SenaeResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying SENAE: declaration=%s", declaration_number)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(SENAE_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='text'], input[name*='declaracion'], input[name*='dae']"
                )
                if search_input:
                    search_input.fill(declaration_number)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                status = ""
                importer = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if "importador" in lower and ":" in stripped and not importer:
                        importer = stripped.split(":", 1)[1].strip()
                    if ("estado" in lower or "status" in lower) and ":" in stripped and not status:
                        status = stripped.split(":", 1)[1].strip()

                if not status:
                    if "levante" in body_lower or "aprobada" in body_lower:
                        status = "Levante autorizado"
                    elif "pendiente" in body_lower:
                        status = "Pendiente"
                    elif "no encontr" in body_lower:
                        status = "No encontrada"
                    else:
                        status = "Consultada"

            return SenaeResult(
                queried_at=datetime.now(),
                declaration_number=declaration_number,
                status=status,
                importer=importer,
                details=f"SENAE query for declaration: {declaration_number}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ec.senae", f"Query failed: {e}") from e
