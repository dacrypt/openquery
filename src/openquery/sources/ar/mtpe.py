"""MTPE employer lookup source — Argentina.

Queries Ministerio de Trabajo for employer registration by CUIT.

URL: https://www.argentina.gob.ar/trabajo
Input: CUIT (custom)
Returns: employer registration status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.mtpe import MtpeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MTPE_URL = "https://www.argentina.gob.ar/trabajo/registrolaboral"


@register
class MtpeSource(BaseSource):
    """Query Argentina Ministerio de Trabajo employer registration by CUIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.mtpe",
            display_name="MTEySS — Registro Laboral de Empleadores",
            description="Argentina Ministerio de Trabajo employer registration lookup by CUIT",
            country="AR",
            url=MTPE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cuit = input.extra.get("cuit", input.document_number).strip()
        if not cuit:
            raise SourceError(
                "ar.mtpe",
                "Provide a CUIT (extra.cuit or document_number)",
            )
        return self._fetch(cuit, audit=input.audit)

    def _fetch(self, cuit: str, audit: bool = False) -> MtpeResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying MTEySS: cuit=%s", cuit)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(MTPE_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                cuit_input = page.query_selector(
                    "input[name*='cuit'], input[id*='cuit'], input[placeholder*='cuit' i], input[type='text']"  # noqa: E501
                )
                if cuit_input:
                    cuit_input.fill(cuit)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        cuit_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                employer_name = ""
                registration_status = ""

                for line in body_text.split("\n"):
                    line_lower = line.lower()
                    if "razón social" in line_lower or "denominación" in line_lower:
                        parts = line.split(":")
                        if len(parts) > 1 and not employer_name:
                            employer_name = parts[1].strip()
                    if "estado" in line_lower or "registrado" in line_lower:
                        parts = line.split(":")
                        if len(parts) > 1 and not registration_status:
                            registration_status = parts[1].strip()

                if not registration_status:
                    if "registrado" in body_lower:
                        registration_status = "Registrado"
                    elif "no registrado" in body_lower:
                        registration_status = "No registrado"

            return MtpeResult(
                queried_at=datetime.now(),
                cuit=cuit,
                employer_name=employer_name,
                registration_status=registration_status,
                details=f"MTEySS query for CUIT: {cuit}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ar.mtpe", f"Query failed: {e}") from e
