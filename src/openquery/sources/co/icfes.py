"""ICFES exam results source — Colombia.

Queries ICFES for exam score results by document number.

URL: https://www.icfes.gov.co/
Input: document number (cedula)
Returns: exam scores and results
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.icfes import IcfesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ICFES_URL = "https://www.icfes.gov.co/resultados-saber-pro"


@register
class IcfesSource(BaseSource):
    """Query ICFES exam results by document number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.icfes",
            display_name="ICFES — Resultados de Exámenes",
            description="Colombian ICFES exam results lookup by document number",
            country="CO",
            url=ICFES_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        documento = input.document_number.strip()
        if not documento:
            raise SourceError("co.icfes", "Document number is required")
        return self._fetch(documento, audit=input.audit)

    def _fetch(self, documento: str, audit: bool = False) -> IcfesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying ICFES: documento=%s", documento)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(ICFES_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                # Look for document input field
                doc_input = page.query_selector(
                    "input[name*='documento'], input[placeholder*='documento' i], "
                    "input[id*='documento'], input[type='text']"
                )
                if doc_input:
                    doc_input.fill(documento)
                    submit = page.query_selector(
                        "button[type='submit'], input[type='submit'], button:has-text('Consultar')"
                    )
                    if submit:
                        submit.click()
                    else:
                        doc_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")

                nombre = ""
                exam_type = ""
                score = ""

                for line in body_text.split("\n"):
                    line_stripped = line.strip()
                    line_lower = line_stripped.lower()
                    if "nombre" in line_lower and not nombre:
                        parts = line_stripped.split(":")
                        if len(parts) > 1:
                            nombre = parts[1].strip()
                    if any(k in line_lower for k in ["saber", "icfes", "examen"]) and not exam_type:
                        exam_type = line_stripped
                    if any(k in line_lower for k in ["puntaje", "puntación", "score"]) and not score:  # noqa: E501
                        parts = line_stripped.split(":")
                        if len(parts) > 1:
                            score = parts[1].strip()

            return IcfesResult(
                queried_at=datetime.now(),
                documento=documento,
                nombre=nombre,
                exam_type=exam_type,
                score=score,
                details=f"ICFES query for document: {documento}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.icfes", f"Query failed: {e}") from e
